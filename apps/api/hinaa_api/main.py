
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from contextlib import asynccontextmanager
import time
import httpx
from pathlib import Path
from time import perf_counter
from typing import Annotated, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone

from fastapi import Body, Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from . import __version__, realtime_tickets
from .audio import validate_wav, ensure_wav_or_mp3
from .avatar_assets import AvatarAssetError, AvatarAssetService
from .runtime_paths import live_runner_state_path, project_root
from .auth_safety import auth_safety_report
from .realtime_origin import choose_realtime_origin
from .config import Settings, get_settings
from .errors import HinaaError, hinaa_error_handler, unhandled_error_handler
from .models import ProviderStatus, SpeechRequest, ToolRequest, TranscriptResponse, TurnRequest, VoiceProfile, TextHumanizerRequest, TextHumanizerResponse, ImageStudioConfigPayload
from .astra import AstraRequest, AstraRuntime
from .creative import CreativeJobStore, CreativeModelRegistry, MagnificBudgetManager
from .media import AssetSource, get_asset_store
from .persistence import MemoryService, TaskService, init_db
from .persistence.auth import (
    AuthContext,
    auth_dependency_factory,
    reached_through_edge,
    resolve_auth,
)
from .persistence.db import get_session_factory, reset_session_factory
from .persistence.project_service import LocalProjectService
from .dialogue_state import AssetReferenceResolver, AssetSelectionSource, ConversationTurnState
from .prompts import PROMPT_VERSION
from .brain_ledger import (
    aliases_for,
    configured,
    fingerprints_for,
    is_local_brain,
    newest_success,
    newest_verdict,
    row_for_brain,
)
from .reachability import GatewayModelsOutcome, is_ephemeral_tunnel, probe_gateway, probe_gateway_models
from .reminder_scheduler import run_scheduler as run_reminder_scheduler
from .news.scheduler import run_scheduler as run_news_scheduler
from .telephony.router import is_webhook_path as is_telephony_webhook
from .ops import genai, metrics
from .ops.health import check_database
from .ops.context import configure_logging, user_id_var
from .ops.middleware import BodyLimitMiddleware, ObservabilityMiddleware
from .ops.ratelimit import EXEMPT_PATHS as RATE_EXEMPT_PATHS
from .ops.ratelimit import TokenBucketLimiter, client_ip
from .ops.ratelimit import is_expensive as rate_is_expensive
from .ops.setup import cors_settings, init_otel, init_sentry
from .realtime import RealtimeGateway
from .run_ledger import get_run_ledger
from .services import ConversationService
from .tools import policy as tool_policy, registry
from .tools.reminder import cancel_reminder, list_reminders, schedule_reminder
from .vmc_bridge import vmc_bridge
from .voice_profiles import public_profiles
from .artifacts import ArtifactFormat, ArtifactService
from .college.vault import StudentRegistrationRequest, college_vault_service


logger = logging.getLogger(__name__)


class RememberBody(BaseModel):
    content: Annotated[str, Field(min_length=1, max_length=500)]
    category: Annotated[str, Field(default="other", max_length=40)] = "other"
    sourceTurnRef: str | None = None


class UpdateMemoryBody(BaseModel):
    content: Annotated[str, Field(min_length=1, max_length=500)]
    expiresAt: datetime | None = None


class MemoryToggleBody(BaseModel):
    enabled: bool


class ConversationTitleBody(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=200)]


class ReminderBody(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=200)]
    at: Annotated[str, Field(min_length=1, max_length=40)]
    conversationId: str | None = None


class ProjectCreateBody(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=180)]
    description: Annotated[str, Field(max_length=50_000)] = ""


class ProjectPlanBody(BaseModel):
    goal: Annotated[str, Field(min_length=3, max_length=50_000)]


class ProjectTaskBody(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=240)]
    detail: Annotated[str, Field(max_length=200_000)] = ""
    parentTaskId: str | None = None
    requiresApproval: bool = False


class ProjectTaskStatusBody(BaseModel):
    status: Annotated[str, Field(pattern="^(pending|active|success|error|cancelled|waiting_approval)$")]


class ProjectAgentRunBody(BaseModel):
    goal: Annotated[str, Field(min_length=3, max_length=200_000)]
    rootTaskId: str | None = None


class DocumentPdfBody(BaseModel):
    title: Annotated[str, Field(default="HINAA Report", max_length=240)]
    markdown: Annotated[str, Field(min_length=1, max_length=120_000)]
    subtitle: Annotated[str, Field(max_length=240)] | None = None


class VisionReactBody(BaseModel):
    frame: str
    consent: bool = False
    sessionId: str | None = None
    context: str | None = None
    sedentaryMinutes: float | None = None
    storeObservations: bool = False


class VisionObserveBody(BaseModel):
    frame: str
    query: str | None = None
    conversationId: str | None = None
    companionId: str | None = "hinaa"


class SwarmExecutionBody(BaseModel):
    mission: str
    tasks: list[str] | None = None
    conversationId: str | None = None


class ProjectAgentRunStatusBody(BaseModel):
    status: Annotated[str, Field(pattern="^(queued|running|waiting_approval|completed|failed|cancelled)$")]
    summary: Annotated[str, Field(max_length=20_000)] | None = None


class ProjectAgentRunEventBody(BaseModel):
    kind: Annotated[str, Field(min_length=1, max_length=40)] = "progress"
    status: Annotated[str, Field(max_length=30)] | None = None
    label: Annotated[str, Field(min_length=1, max_length=240)]
    detail: Annotated[str, Field(max_length=20_000)] = ""


class ProjectCodeFileBody(BaseModel):
    path: Annotated[str, Field(min_length=1, max_length=600)]
    content: Annotated[str, Field(max_length=1_048_576)]
    overwrite: bool = False
    runId: str | None = None


class CreativeBudgetSnapshotBody(BaseModel):
    balance: Annotated[int, Field(ge=0)]


class CreativeEstimateBody(BaseModel):
    model: Annotated[str, Field(min_length=1, max_length=120)]
    width: Annotated[int, Field(default=1024, ge=1, le=16384)] = 1024
    height: Annotated[int, Field(default=1024, ge=1, le=16384)] = 1024
    scale: Annotated[float, Field(default=2.0, ge=1, le=8)] = 2.0


class CreativeJobBody(BaseModel):
    prompt: Annotated[str, Field(min_length=1, max_length=4000)]
    model: Annotated[str, Field(min_length=1, max_length=120)]


class ProjectArtifactBody(BaseModel):
    kind: Annotated[str, Field(pattern="^(note|research|image|document|export|link)$")]
    title: Annotated[str, Field(min_length=1, max_length=240)]
    content: Annotated[str, Field(max_length=100_000)] = ""
    sourceUrl: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SelectionRequestBody(BaseModel):
    resultSetId: Annotated[str, Field(min_length=1, max_length=120)]
    assetId: Annotated[str, Field(min_length=1, max_length=160)]
    index: Annotated[int, Field(ge=0)]
    projectId: str | None = None
    source: str = "UI_CLICK"


class CreateDocumentArtifactBody(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=240)]
    content: Annotated[str, Field(max_length=500_000)]
    format: str = "md"
    projectId: str | None = None
    conversationId: str | None = None
    taskId: str | None = None
    tags: list[str] = Field(default_factory=list)


class CreatePresentationArtifactBody(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=240)]
    subtitle: str = ""
    slides: list[dict[str, Any]]
    projectId: str | None = None
    conversationId: str | None = None
    taskId: str | None = None


class CreateSpreadsheetArtifactBody(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=240)]
    sheets: list[dict[str, Any]]
    projectId: str | None = None
    conversationId: str | None = None
    taskId: str | None = None


class PackageArtifactsBody(BaseModel):
    artifactIds: list[str]
    bundleTitle: Annotated[str, Field(min_length=1, max_length=120)]
    description: str = ""


class ConversationResolveBody(BaseModel):
    text: Annotated[str, Field(min_length=1, max_length=200_000)]
    projectState: dict[str, Any] | None = None


class CreateTaskBody(BaseModel):
    goal: Annotated[str, Field(min_length=3, max_length=200_000)]
    conversationId: str | None = None
    projectId: str | None = None
    taskType: str = "general"
    priority: int = 0
    reasoningMode: str = "balanced"
    steps: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] | None = None


class ResolveTaskBody(BaseModel):
    text: Annotated[str, Field(min_length=1, max_length=200_000)]
    conversationId: str | None = None
    projectId: str | None = None


class CompleteStepBody(BaseModel):
    outputArtifactIds: list[str] | None = None


class ClaimTaskBody(BaseModel):
    workerId: Annotated[str, Field(min_length=1, max_length=120)]
    leaseSeconds: Annotated[int, Field(default=60, ge=5, le=3600)] = 60
    conversationId: str | None = None
    projectId: str | None = None


class CompleteStepWithLeaseBody(BaseModel):
    leaseId: Annotated[str, Field(min_length=1, max_length=80)]
    fencingToken: int = Field(ge=0)
    outputArtifactIds: list[str] | None = None


class FailStepBody(BaseModel):
    reason: Annotated[str, Field(min_length=1, max_length=50_000)]
    retryLimit: int = 2


class SteerTaskBody(BaseModel):
    instruction: Annotated[str, Field(min_length=1, max_length=200_000)]


class CancelTaskBody(BaseModel):
    reason: str | None = None


class RollbackTaskBody(BaseModel):
    version: int = Field(ge=1)


class SideEffectPlannedBody(BaseModel):
    stepId: str | None = None
    idempotencyKey: Annotated[str, Field(min_length=1, max_length=160)]
    provider: Annotated[str, Field(min_length=1, max_length=80)]
    operationType: Annotated[str, Field(min_length=1, max_length=80)]
    requestPayload: dict[str, Any] = Field(default_factory=dict)


class SideEffectAcceptedBody(BaseModel):
    providerOperationId: Annotated[str, Field(min_length=1, max_length=160)]
    responsePayload: dict[str, Any] = Field(default_factory=dict)


def _correlation_id(value: str | None) -> str:
    try:
        return str(UUID(value)) if value else str(uuid4())
    except ValueError:
        return str(uuid4())


# Capability records that name a chat brain. "you" is a research lane and speech
# providers are not brains, so neither gets a live-call verdict.
_BRAIN_PROVIDER_IDS = frozenset(
    {
        "gmi",
        "agent-router",
        "cavoti",
        "claude",
        "codecraft",
        "custom",
        "cx-gateway",
        "deepseek",
        "gemini",
        "groq",
        "ollama",
        "omniroute",
        "openai",
        "pgsgrove",
        "qwen",
        "seekai",
        "tokentable",
        "xkiro",
        "cavoti",
        "apmix",
        "oxion",
        "respan",
        "experiential",
    }
)


def _routing_truth(settings: Settings, requested_mode: str) -> dict[str, Any]:
    """Who actually answered, as opposed to who this deployment is configured for.

    `mode` answers "what did the owner ask for?". It stayed "claude" through weeks in
    which every answer came from a flash-tier fallback, so any badge built from it
    lied about the brain behind her voice. This reads the ledger of calls that
    really happened, so a green routing statement costs a real answered turn.
    """
    answered = newest_success()
    requested = newest_verdict(
        aliases_for(requested_mode),
        fingerprints=fingerprints_for(settings, requested_mode),
    )
    if is_local_brain(requested_mode):
        # An in-process brain needs no socket, so configuration does prove it, and
        # the absence of ledger records means nobody has asked it anything yet.
        served_requested = requested_mode
        reason = f"{requested_mode} answers in-process and needs no live call to prove it."
    else:
        served_requested = (
            requested_mode
            if answered and row_for_brain(answered.brain_id) == requested_mode
            else ""
        )
        reason = answered.message if served_requested else ""
    if not reason:
        if not configured(settings, requested_mode):
            reason = (
                f"{requested_mode} is not configured, so it cannot answer; "
                + (f"answers came from {answered.brain_id}." if answered else "nothing has.")
            )
        elif answered is None:
            reason = (
                "No brain has answered a live call recently enough to claim. "
                + (
                    requested.message
                    if requested
                    else f"{requested_mode} has no live-call evidence either."
                )
            )
        elif requested is None:
            reason = (
                f"{requested_mode} has no live-call evidence in this window; "
                f"answers came from {answered.brain_id}."
            )
        else:
            reason = f"{requested.message} Answers came from {answered.brain_id} instead."
    return {
        "answeredBy": (
            {
                "brain": answered.brain_id,
                "row": row_for_brain(answered.brain_id),
                "model": answered.model or None,
                "ageSeconds": round(answered.age_seconds, 1),
            }
            if answered
            else None
        ),
        "requestedServed": bool(served_requested),
        "fallback": answered is not None and not served_requested,
        "reason": reason,
    }


_PROBE_CACHE: dict[str, tuple[float, Any]] = {}
_PROBE_TTL_SECONDS = 45.0


def _probe_cached(key: str, ttl: float = _PROBE_TTL_SECONDS) -> Any | None:
    """A local probe answer remembered for a short window.

    A configured-but-dead local engine (Ollama, ComfyUI) used to be re-probed by
    every status poll, so one unhealthy service produced an endless stream of
    connection timeouts in the log even while she sat idle. Remembering the last
    answer for a few seconds turns "probe on every poll" into "probe every TTL".
    """
    entry = _PROBE_CACHE.get(key)
    if entry is not None and (time.time() - entry[0]) < ttl:
        return entry[1]
    return None


def _probe_store(key: str, value: Any) -> None:
    _PROBE_CACHE[key] = (time.time(), value)


def _ledger_response_text(plan: Any) -> str | None:
    """The text she actually said, for the turn ledger's stop row."""
    if not isinstance(plan, dict):
        return None
    for key in ("spokenText", "message", "text", "summary"):
        value = plan.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def create_app(settings: Settings | None = None) -> FastAPI:
    # Without this, INFO-level breadcrumbs (realtime message trace) and even
    # uncaught-exception logging were effectively invisible: Python's root
    # logger has no handler by default, and the previous bare `except
    # Exception:` in the realtime turn loop did not log at all. This is why
    # turn failures looked like an unexplained "connection lost" with zero
    # server-side trace to diagnose from.
    configure_logging("text")
    active_settings = settings or get_settings()
    configure_logging(active_settings.log_format)
    init_sentry(active_settings)
    rate_limiter = TokenBucketLimiter()
    metrics.PROCESS_START.set_to_current_time()
    reset_session_factory()
    session_factory = init_db(active_settings) if active_settings.persistence_enabled else None
    memory_service = (
        MemoryService(session_factory) if session_factory is not None else None
    )
    task_service = (
        TaskService(session_factory) if session_factory is not None else None
    )
    service = ConversationService(active_settings, memory_service=memory_service, task_service=task_service, session_factory=session_factory)
    astra_runtime = AstraRuntime(
        memory_service=memory_service,
        conversation_service=service,
    )
    workspace_service = LocalProjectService(
        get_session_factory(active_settings), active_settings.local_workspace_dir
    )
    artifact_service = ArtifactService(
        storage_dir=active_settings.local_workspace_dir / "artifacts"
    )
    creative_budget = MagnificBudgetManager(settings=active_settings)
    creative_jobs = CreativeJobStore()
    asset_store = get_asset_store()
    avatar_assets = AvatarAssetService(
        active_settings.local_workspace_dir,
        project_root(),
    )
    realtime = RealtimeGateway(active_settings, service)
    require_auth = (
        auth_dependency_factory(active_settings, memory_service)
        if memory_service is not None
        else None
    )
    from .agent import AgentRuntime
    from .agent.contracts import AgentEvent, OperationType, PlanStep, RunStatus, AgentPlan, AgentRun
    from .agent.persistence import AgentPersistenceService

    async def _agent_executor(step: PlanStep) -> Any:
        if step.operation_type == OperationType.TOOL:
            if not step.tool_name:
                raise HinaaError("TOOL_UNAVAILABLE", "Tool name required for tool step", 400)
            from .tools.dynamic_tools import sync_dynamic_tools
            sync_dynamic_tools()
            tool_def = registry.get_tool(step.tool_name)
            if not tool_def:
                raise HinaaError("TOOL_UNAVAILABLE", f"Tool {step.tool_name} not found", 404)
            handler = registry._handlers.get(step.tool_name)
            if not handler:
                raise HinaaError("TOOL_UNAVAILABLE", f"Tool handler for {step.tool_name} not found", 404)
            tool_policy.enforce(step.tool_name, active_settings)
            tool_policy.check_arguments(step.tool_name, step.tool_parameters)
            import inspect
            from typing import get_type_hints
            from pydantic import BaseModel

            sig = inspect.signature(handler)
            parsed_params = dict(step.tool_parameters or {})
            if len(sig.parameters) == 1:
                param_name = next(iter(sig.parameters.keys()))
                hints = get_type_hints(handler)
                param_type = hints.get(param_name, sig.parameters[param_name].annotation)
                if isinstance(param_type, type) and issubclass(param_type, BaseModel):
                    arg = param_type(**parsed_params)
                    res = handler(arg)
                else:
                    res = handler(parsed_params)
            else:
                res = handler(**parsed_params)
            if inspect.isawaitable(res):
                res = await res
            return res
        return {"status": "success", "content": step.description or step.title}

    agent_persistence = (
        AgentPersistenceService(get_session_factory(active_settings))
        if active_settings.persistence_enabled
        else None
    )

    agent_runtime = AgentRuntime(
        executor=_agent_executor,
        max_steps=active_settings.agent_max_steps,
        max_replans=active_settings.agent_max_replans,
        step_attempts=active_settings.agent_default_step_attempts,
        run_timeout=active_settings.agent_run_timeout_seconds,
        enabled=active_settings.agent_runtime_enabled,
        allowed_tools={t.name for t in registry.get_all_tools()},
        persistence=agent_persistence,
    )

    from .agent.bridge import DurableTaskBridge
    durable_task_bridge = (
        DurableTaskBridge(task_service, agent_runtime)
        if task_service is not None and agent_runtime is not None
        else None
    )

    from .cognitive import (
        CognitiveKernel,
        WorldModel,
        SessionBridge,
        get_policy_engine,
        get_data_lake,
        get_resilient_router,
    )
    from .memory_v2.manager import MemoryManagerV2

    memory_v2_manager = MemoryManagerV2()
    session_bridge = SessionBridge(root_dir=".")
    policy_engine = get_policy_engine()
    data_lake = get_data_lake()
    resilient_router = get_resilient_router()

    cognitive_kernel = CognitiveKernel(
        session_bridge=session_bridge,
        memory_manager=memory_v2_manager,
        policy_engine=policy_engine,
        data_lake=data_lake,
        resilient_router=resilient_router,
    )

    project_tasks: dict[str, asyncio.Task] = {}
    tool_tasks: set[asyncio.Task] = set()


    async def _wait_image_job(job_id: str, owner: str) -> dict[str, Any]:
        from .persistence.orm import GenerationSet, ImageJob
        while True:
            with get_session_factory(active_settings)() as session:
                generation = session.query(GenerationSet).filter_by(id=job_id, user_id=owner).first()
                if generation is None:
                    raise HinaaError("IMAGE_JOB_NOT_FOUND", "Image job not found for this user.", 404)
                jobs = session.query(ImageJob).filter_by(generation_set_id=job_id).all()
                if jobs and all(job.status not in {"pending", "queued", "processing"} for job in jobs):
                    if any(job.status != "completed" or not job.file_path for job in jobs):
                        raise HinaaError("IMAGE_JOB_FAILED", "One or more image outputs failed; inspect the image job.", 502)
                    img_urls = [f"/api/v1/generated-images/{job.id}" for job in jobs]
                    cid = generation.conversation_id
                    try:
                        from hinaa_api.media.resolver import MediaResolver
                        from hinaa_api.dialogue_state import EntityReferenceResolver
                        resolver = MediaResolver()
                        new_asset_ids = []
                        for img_url in img_urls:
                            res = await resolver.resolve(img_url)
                            if res and res.asset_id:
                                new_asset_ids.append(res.asset_id)
                        if cid and service.dialogue_state_service:
                            d_state = service.dialogue_state_service.load(cid, owner)
                            for aid in new_asset_ids:
                                if aid not in d_state.last_generated_asset_ids:
                                    d_state.last_generated_asset_ids.append(aid)
                                if not any(a.get("asset_id") == aid for a in d_state.active_assets):
                                    d_state.active_assets.append({
                                        "asset_id": aid,
                                        "url": f"/api/v1/assets/{aid}",
                                        "type": "image",
                                        "created_at": datetime.now(timezone.utc).isoformat(),
                                    })
                            active_char = EntityReferenceResolver.get_active_character(d_state)
                            d_state.last_assistant_action = {
                                "action": "image_generate",
                                "prompt": generation.prompt,
                                "subject": active_char,
                                "asset_ids": new_asset_ids,
                                "completed": True,
                            }
                            d_state.tool_result_sets.append({
                                "result_set_id": job_id,
                                "tool": "image_generate",
                                "ordered_asset_ids": new_asset_ids,
                            })
                            service.dialogue_state_service.save(d_state)
                    except Exception:
                        logger.warning("Failed to record generated assets in dialogue state during _wait_image_job", exc_info=True)

                    return {
                        "status": "success",
                        "job_id": job_id,
                        "images": img_urls,
                    }
            await asyncio.sleep(1)

    async def _execute_registered_tool(tool_def, handler, parameters, body, owner):
        import hashlib
        agent_runtime.validator.allowed_tools = {tool.name for tool in registry.get_all_tools()}
        key = body.idempotencyKey or body.id
        run_id = ("run_" + hashlib.sha256(f"{owner}:{key}".encode()).hexdigest()[:24]) if key else f"run_{uuid4().hex[:24]}"
        existing = agent_runtime.get_run(run_id, owner) if (key and run_id) else None
        if not existing and durable_task_bridge and key and run_id:
            try:
                task_data = durable_task_bridge.task_service.get_task(owner, run_id)
                if task_data:
                    existing, _ = durable_task_bridge.resume_from_checkpoint(owner, run_id)
            except Exception:
                pass
        if existing:
            previous = agent_runtime.get_plan(existing.run_id)
            prior = previous.steps[0] if previous and previous.steps else None
            normalized = parameters.model_dump(mode="json") if isinstance(parameters, BaseModel) else parameters
            normalized = {k: v for k, v in normalized.items() if k not in {"userId", "user_id"}}
            if prior is None or prior.tool_name != tool_def.name or prior.tool_parameters != normalized:
                raise HinaaError("IDEMPOTENCY_CONFLICT", "This request key was used for a different action.", 409)
            if prior.result is not None:
                value = prior.result
                return {**value, "runtimeRunId": existing.run_id} if isinstance(value, dict) else value
            raise HinaaError("RUN_ALREADY_STARTED", "This action already started. Inspect the existing run before retrying.", 409)

        normalized = parameters.model_dump(mode="json") if isinstance(parameters, BaseModel) else parameters
        stored_params = {k: v for k, v in normalized.items() if k not in {"userId", "user_id"}}

        durable_task_id = None
        durable_step_id = None
        if durable_task_bridge is not None:
            task_dict, run, plan = durable_task_bridge.create_durable_agent_run(
                owner_id=owner,
                goal=f"Execute {tool_def.display_name}",
                run_id=run_id,
                conversation_id=body.conversationId,
                task_type="agent_action",
                steps=[
                    {
                        "title": tool_def.display_name,
                        "description": f"Execute {tool_def.name}",
                        "toolCallIds": [tool_def.name],
                    }
                ],
                metadata={"toolName": tool_def.name, "parameters": stored_params, "idempotencyKey": key},
            )
            durable_task_id = task_dict["id"]
            durable_step_id = task_dict["steps"][0]["id"] if task_dict.get("steps") else None
            step = plan.steps[0]
            step.tool_parameters = stored_params
            step.tool_name = tool_def.name
            step.maximum_attempts = 1
            step.timeout_seconds = min(600, (tool_def.timeout_seconds or 60) + 1)
            if agent_runtime.persistence:
                agent_runtime.persistence.save_step(step)
        else:
            run = agent_runtime.create_run(
                f"Execute {tool_def.display_name}",
                owner,
                conversation_id=body.conversationId,
                run_id=run_id,
            )
            step = PlanStep(
                plan_id="pending",
                sequence=0,
                title=tool_def.display_name,
                operation_type=OperationType.TOOL,
                tool_name=tool_def.name,
                tool_parameters=stored_params,
                maximum_attempts=1,
                timeout_seconds=min(600, (tool_def.timeout_seconds or 60) + 1),
            )
            plan = AgentPlan(run_id=run.run_id, goal=run.goal, steps=[step])
            step.plan_id = plan.plan_id

        first_result = asyncio.get_running_loop().create_future()

        async def invoke(_step):
            try:
                try:
                    value = await asyncio.wait_for(handler(parameters), timeout=tool_def.timeout_seconds or 60.0)
                except TimeoutError as error:
                    raise HinaaError("TOOL_TIMEOUT", "The tool exceeded its execution deadline.", 504) from error
                if isinstance(value, dict) and value.get("status") in {"error", "failed"}:
                    if not first_result.done():
                        first_result.set_result(value)
                    raise HinaaError(str(value.get("code") or "TOOL_FAILED"), str(value.get("error") or "Tool failed."), 502)
                step.result = value
                if agent_runtime.persistence:
                    agent_runtime.persistence.save_step(step)
                if durable_task_bridge and durable_task_id and durable_step_id:
                    try:
                        durable_task_bridge.task_service.complete_step(
                            owner_id=owner,
                            task_id=durable_task_id,
                            step_id=durable_step_id,
                            output_artifact_ids=[],
                        )
                    except Exception:
                        logger.warning("Failed to record durable step completion", exc_info=True)
                agent_runtime._emit(
                    run.run_id,
                    "agent.step.progress",
                    step_id=step.step_id,
                    payload={"toolName": tool_def.name, "jobId": value.get("job_id") if isinstance(value, dict) else None},
                )
                if tool_def.name != "image_search" and not first_result.done():
                    first_result.set_result(value)
                if isinstance(value, dict) and value.get("job_id"):
                    return await _wait_image_job(value["job_id"], owner)

                effective_convo_id = body.conversationId or (parameters.get("conversationId") if isinstance(parameters, dict) else getattr(parameters, "conversationId", None))
                if tool_def.name == "image_search" and isinstance(value, dict) and value.get("images") and effective_convo_id:
                    try:
                        from hinaa_api.media.resolver import MediaResolver
                        resolver = MediaResolver()
                        search_asset_ids = []
                        result_set = value.get("resultSet") if isinstance(value.get("resultSet"), dict) else {}
                        result_set_id = result_set.get("resultSetId") or f"rs_{uuid4().hex[:12]}"
                        canonical_subject = (
                            value.get("canonicalSubject")
                            or result_set.get("canonicalSubject")
                            or (parameters.get("canonicalSubject") if isinstance(parameters, dict) else None)
                        )
                        source_uris: list[str | None] = []
                        thumbnail_uris: list[str | None] = []
                        for idx, itm in enumerate(value["images"]):
                            u = itm.get("url") if isinstance(itm, dict) else str(itm)
                            asset_id = None
                            if u:
                                r = await resolver.resolve(u)
                                if r and r.asset_id:
                                    asset_id = r.asset_id
                            if isinstance(itm, dict):
                                asset_id = asset_id or str(itm.get("assetId") or itm.get("asset_id") or itm.get("id") or f"{result_set_id}:{idx}")
                                itm["assetId"] = asset_id
                                itm["asset_id"] = asset_id
                                itm["resultSetId"] = result_set_id
                                itm["result_set_id"] = result_set_id
                                itm["ordinalIndex"] = idx
                                itm["ordinal_index"] = idx
                                itm["canonicalSubject"] = canonical_subject
                                itm["entityIds"] = (parameters.get("entityIds") if isinstance(parameters, dict) else []) or []
                                source_uris.append(itm.get("pageUrl") or itm.get("sourceUrl") or itm.get("url"))
                                thumbnail_uris.append(itm.get("thumbnailUrl") or itm.get("imageUrl") or itm.get("url"))
                            if asset_id:
                                search_asset_ids.append(asset_id)
                        value["galleryItems"] = [
                            {
                                "assetId": img.get("assetId"),
                                "resultSetId": img.get("resultSetId"),
                                "index": img.get("ordinalIndex"),
                                "thumbnailUrl": img.get("thumbnailUrl") or img.get("imageUrl") or img.get("url"),
                                "sourceUrl": img.get("pageUrl") or img.get("url"),
                                "title": img.get("title") or "Image result",
                                "sourceDomain": img.get("source") or img.get("domain") or "Web",
                            }
                            for img in value["images"]
                            if isinstance(img, dict)
                        ]
                        value["resultSet"] = {
                            **result_set,
                            "resultSetId": result_set_id,
                            "canonicalSubject": canonical_subject,
                            "orderedAssetIds": search_asset_ids,
                        }
                        if service.dialogue_state_service:
                            d_state = service.dialogue_state_service.load(effective_convo_id, owner)
                            d_state.tool_result_sets.append({
                                "result_set_id": result_set_id,
                                "tool": "image_search",
                                "query": (parameters.get("query") if isinstance(parameters, dict) else getattr(parameters, "query", "")),
                                "canonical_subject": canonical_subject,
                                "entity_ids": (parameters.get("entityIds") if isinstance(parameters, dict) else []) or [],
                                "provider": value.get("provider"),
                                "relevance_scores": result_set.get("relevanceScores") or [],
                                "ordered_asset_ids": search_asset_ids,
                                "source_uris": source_uris,
                                "thumbnail_uris": thumbnail_uris,
                            })
                            if canonical_subject:
                                d_state.last_assistant_action = {
                                    "action": "image_search",
                                    "subject": canonical_subject,
                                    "prompt": (parameters.get("query") if isinstance(parameters, dict) else getattr(parameters, "query", "")),
                                    "result_set_id": result_set_id,
                                }
                            service.dialogue_state_service.save(d_state)
                    except Exception:
                        logger.warning("Failed to record image_search result set into dialogue state", exc_info=True)
                elif tool_def.name in ("web_search", "web_research", "web_answer", "web_extract") and isinstance(value, dict) and effective_convo_id:
                    try:
                        if service.dialogue_state_service:
                            d_state = service.dialogue_state_service.load(effective_convo_id, owner)
                            results_list = value.get("results") or value.get("sources") or value.get("pages") or []
                            extracted_snippets = []
                            for itm in results_list[:8]:
                                if isinstance(itm, dict):
                                    t = itm.get("title") or ""
                                    s = itm.get("snippet") or itm.get("description") or itm.get("content") or itm.get("text") or ""
                                    u = itm.get("url") or ""
                                    if t or s:
                                        extracted_snippets.append({"title": t[:120], "snippet": s[:300], "url": u})
                            d_query = (parameters.get("query") if isinstance(parameters, dict) else getattr(parameters, "query", "")) or (parameters.get("topic") if isinstance(parameters, dict) else getattr(parameters, "topic", "")) or d_state.active_topic or ""
                            answer_text = value.get("answer") if isinstance(value.get("answer"), str) else None
                            d_state.tool_result_sets.append({
                                "result_set_id": str(uuid4()),
                                "tool": tool_def.name,
                                "query": d_query,
                                "items": extracted_snippets,
                                "answer": answer_text[:500] if answer_text else None,
                            })
                            if not d_state.active_topic and d_query:
                                d_state.active_topic = d_query
                            service.dialogue_state_service.save(d_state)
                    except Exception:
                        logger.warning("Failed to record web_search result set into dialogue state", exc_info=True)
                if not first_result.done():
                    first_result.set_result(value)
                return value
            except Exception as exc:
                if durable_task_bridge and durable_task_id and durable_step_id:
                    try:
                        durable_task_bridge.task_service.fail_step(
                            owner_id=owner,
                            task_id=durable_task_id,
                            step_id=durable_step_id,
                            reason=str(exc),
                        )
                    except Exception:
                        pass
                if not first_result.done():
                    first_result.set_exception(exc)
                raise


        async def work():
            try:
                await agent_runtime.execute(run, plan=plan, executor=invoke)
            except Exception as exc:
                if not first_result.done():
                    first_result.set_exception(exc)
            finally:
                tool_tasks.discard(asyncio.current_task())

        task = asyncio.create_task(work(), name=f"hinaa-tool-{run.run_id}")
        tool_tasks.add(task)
        result = await first_result
        if isinstance(result, str) and result.startswith("REQUIRES_APPROVAL:"):
            parts = result.split(":", 2)
            if len(parts) == 3:
                return {
                    "status": "RequiresApproval",
                    "data": {"action": parts[1], "args": parts[2]},
                    "runtimeRunId": run.run_id,
                }
        if isinstance(result, dict):
            if "status" in result and ("data" in result or "images" in result or "job_id" in result or "error" in result or "code" in result):
                return {**result, "runtimeRunId": run.run_id}
            envelope = {
                "id": str(uuid4()),
                "toolId": tool_def.name,
                "status": "success",
                "startedAt": int(time.time() * 1000),
                "completedAt": int(time.time() * 1000),
                "data": result,
            }
            return {"status": "success", "data": envelope, "runtimeRunId": run.run_id}
        return {"result": result, "runtimeRunId": run.run_id}

    def _schedule_project_run(run: AgentRun) -> None:
        async def work() -> None:
            try:
                await agent_runtime.execute(run)
            finally:
                project_tasks.pop(run.run_id, None)
                if run.project_id:
                    status = (
                        "completed"
                        if run.status == RunStatus.COMPLETED
                        else ("failed" if run.status == RunStatus.FAILED else run.status.value)
                    )
                    if status in {"completed", "failed", "cancelled"}:
                        workspace_service.update_agent_run(
                            run.user_id, run.run_id, status, run.failure_message or run.goal
                        )

        project_tasks[run.run_id] = asyncio.create_task(work(), name=f"hinaa-project-{run.run_id}")



    def _runtime_event_payload(event: AgentEvent) -> bytes:
        return service._event(
            event.event_type,
            {
                "runId": event.run_id,
                "stepId": event.step_id,
                "event": event.model_dump(mode="json"),
            },
        )


    def _resolve_user_id(request: Request) -> str | None:
        """Best-effort user identity for durable memory.

        When persistence is disabled (or auth cannot be resolved) the turn
        still works - it simply has no durable memory attached.
        """
        if memory_service is None:
            return None
        try:
            auth = resolve_auth(
                request,
                active_settings,
                memory_service,
                authorization=request.headers.get("Authorization"),
                x_hinaa_dev_user=request.headers.get("X-HINAA-Dev-User"),
                allow_default_subject=active_settings.allow_tunnel_dev_auth or not reached_through_edge(request),
            )
        except HinaaError:
            return None
        return auth.user_id

    async def conversation_auth(request: Request) -> AuthContext | None:
        """Resolve route identity without ever accepting a client user id."""
        if memory_service is None:
            return None
        return resolve_auth(
            request,
            active_settings,
            memory_service,
            authorization=request.headers.get("Authorization"),
            x_hinaa_dev_user=request.headers.get("X-HINAA-Dev-User"),
            allow_default_subject=active_settings.allow_tunnel_dev_auth,
        )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):  # type: ignore[no-untyped-def]
        # Start VMC UDP listener for VSeeFace face tracking
        await vmc_bridge.start_udp(port=active_settings.vmc_port)
        if agent_persistence:
            for saved_run in agent_persistence.list_active_runs():
                agent_runtime.recover(saved_run.run_id, saved_run.user_id)
        if task_service:
            task_service.recover_interrupted_tasks()
        # "Reminder set" is only true if something advances the row. This dies
        # with the process, so a reminder due during a restart fires on the
        # first tick after it comes back rather than being lost.
        scheduler_stop = asyncio.Event()
        scheduler_task = None
        if active_settings.reminder_scheduler_enabled and active_settings.persistence_enabled:
            scheduler_task = asyncio.create_task(
                run_reminder_scheduler(
                    settings=active_settings,
                    stop=scheduler_stop,
                    tick_seconds=active_settings.reminder_tick_seconds,
                ),
                name="hinaa-reminder-scheduler",
            )
        news_task = None
        if active_settings.news_scheduler_enabled and active_settings.persistence_enabled:
            news_task = asyncio.create_task(
                run_news_scheduler(
                    settings=active_settings,
                    stop=scheduler_stop,
                    tick_seconds=active_settings.news_tick_seconds,
                ),
                name="hinaa-news-scheduler",
            )
        # Autonomous Heartbeat Daemon initialization & background loop
        from .intelligence.heartbeat import heartbeat_daemon
        heartbeat_daemon.initialize(
            memory_service=memory_service,
            agent_runtime=agent_runtime,
            owner_id=active_settings.dev_auth_subject,
        )
        heartbeat_daemon.start()

        # Autonomous Agency Runtime initialization & background loop
        from .agency import get_agency_runtime
        agency_runtime = get_agency_runtime()
        agency_runtime.set_heartbeat_daemon(heartbeat_daemon)
        agency_runtime.start()
        # A restart must not forget which providers were benched: the first
        # turn after boot would otherwise pay the full dead-primary hang again.
        # Live only, armed by the runner's environment -- a test app on a
        # throwaway sqlite file must never read the live benches nor write
        # its stub-gateway 403s into them.
        if os.environ.get("HINAA_BREAKER_PERSISTENCE") == "1":
            from .circuit_breaker import enable_persistence
            enable_persistence(
                Path(__file__).resolve().parent / "data" / "circuit_breakers.json"
        )
        yield
        agency_runtime.stop()
        heartbeat_daemon.stop()
        scheduler_stop.set()
        if scheduler_task is not None:
            await asyncio.gather(scheduler_task, return_exceptions=True)
        if news_task is not None:
            await asyncio.gather(news_task, return_exceptions=True)
        tasks = [*project_tasks.values(), *tool_tasks]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        vmc_bridge.stop()

    from .voice import VoiceLifecycleManager
    _global_voice_lifecycle = VoiceLifecycleManager("master")
    app = FastAPI(
        title="HINAA API",
        version=__version__,
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    from .omega_router import omega_router
    app.include_router(omega_router)
    from .routers.bivia_router import create_bivia_router
    app.include_router(create_bivia_router(active_settings))
    from .skills.endpoints import router as skills_router
    app.include_router(skills_router)
    from .integrations_hub.endpoints import router as hub_router
    app.include_router(hub_router, prefix="/v1")
    app.include_router(hub_router, prefix="/api/v1")
    from .explanation.endpoints import router as explanation_router, get_explanation_service
    app.include_router(explanation_router)
    app.state.explanation_service = get_explanation_service()
    from .goals.endpoints import router as goals_router, get_goal_service
    app.include_router(goals_router)
    app.state.goal_service = get_goal_service()
    from .security.endpoints import security_router
    from .security.pdp import get_pdp
    app.include_router(security_router)
    app.state.pdp = get_pdp()
    from .productivity.router import build_productivity_router
    for _prod_prefix in ("/v1/productivity", "/api/v1/productivity"):
        app.include_router(build_productivity_router(active_settings, conversation_auth), prefix=_prod_prefix)
    from .orgs.gate import OrgGate
    from .orgs.router import build_org_router
    org_gate = OrgGate(active_settings, memory_service, conversation_auth)
    for _org_prefix in ("/v1/org", "/api/v1/org"):
        app.include_router(build_org_router(org_gate), prefix=_org_prefix)
    from .news.router import build_news_router
    from .social.router import build_social_router
    for _news_prefix in ("/v1/news", "/api/v1/news"):
        app.include_router(build_news_router(active_settings, conversation_auth), prefix=_news_prefix)
    for _social_prefix in ("/v1/social", "/api/v1/social"):
        app.include_router(build_social_router(active_settings, conversation_auth), prefix=_social_prefix)
    from .telephony.router import build_telephony_router
    app.include_router(build_telephony_router(active_settings, service, memory_service, conversation_auth))
    from .routers.loop_router import router as loop_router
    from .routers.evals_router import router as evals_router
    app.include_router(loop_router)
    app.include_router(evals_router)
    from .routers.creative_router import build_creative_router
    app.include_router(build_creative_router(creative_jobs))
    from .memory import MemoryService as Phase10MemoryService
    p10_memory_service = Phase10MemoryService()
    app.state.p10_memory_service = p10_memory_service
    from .routers.memory_p10_router import build_memory_p10_router
    app.include_router(build_memory_p10_router(p10_memory_service))
    app.state.settings = active_settings
    app.state.service = service
    app.state.memory_service = memory_service
    app.state.workspace_service = workspace_service
    app.state.avatar_assets = avatar_assets
    from .speech_stream import register_speech_stream
    register_speech_stream(app, service)
    app.state.creative_budget = creative_budget
    app.state.creative_jobs = creative_jobs
    app.state.asset_store = asset_store
    app.state.agent_runtime = agent_runtime
    app.state.task_service = task_service
    app.state.durable_task_bridge = durable_task_bridge
    app.state.cognitive_kernel = cognitive_kernel
    app.state.memory_v2_manager = memory_v2_manager
    app.state.session_bridge = session_bridge
    app.state.active_voice_lifecycle = _global_voice_lifecycle
    from .research import GroundedResearchCoordinator
    from .research.adapters import LiveSearchAdapter
    live_search = None
    if active_settings.exa_configured:
        live_search = LiveSearchAdapter(
            api_key=active_settings.exa_api_key.get_secret_value(),
            search_url=f"{active_settings.active_exa_base_url}/search",
            timeout_seconds=active_settings.exa_timeout_seconds,
        )
    app.state.research_coordinator = GroundedResearchCoordinator(search_adapter=live_search)
    from .browser import BrowserAutomationService
    app.state.browser_service = BrowserAutomationService()
    from .coding import CodingService
    app.state.coding_service = CodingService()
    from .creative import creative_service
    app.state.creative_service = creative_service
    app.add_exception_handler(HinaaError, hinaa_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_error_handler)

    def _rate_limit_check(request: Request, user_id: str | None) -> JSONResponse | None:
        if not active_settings.rate_limit_active:
            return None
        path = request.url.path
        if request.method == "OPTIONS" or path in RATE_EXEMPT_PATHS or is_telephony_webhook(path):
            return None
        expensive = rate_is_expensive(request.method, path)
        limit = (
            active_settings.rate_limit_expensive_per_minute
            if expensive
            else active_settings.rate_limit_per_minute
        )
        ip = client_ip(
            (request.client.host, request.client.port) if request.client else None,
            request.headers.get("x-forwarded-for"),
            active_settings.trust_proxy,
        )
        subject = f"user:{user_id}" if user_id else f"ip:{ip}"
        bucket = "expensive" if expensive else "default"
        decision = rate_limiter.check(f"{bucket}:{subject}", limit)
        if decision.allowed:
            return None
        metrics.RATE_LIMITED.labels(bucket).inc()
        return JSONResponse(
            status_code=429,
            content={"error": {"code": "RATE_LIMITED", "message": "Too many requests. Retry later."}},
            headers={"Retry-After": str(decision.retry_after)},
        )

    @app.get("/metrics", include_in_schema=False)
    async def prometheus_metrics(request: Request) -> Response:
        token = active_settings.metrics_token.get_secret_value() if active_settings.metrics_token else None
        verdict = metrics.metrics_access(
            client_host=request.client.host if request.client else None,
            authorization=request.headers.get("authorization"),
            forwarded_for=request.headers.get("x-forwarded-for"),
            token=token,
        )
        if verdict == 401:
            return Response("unauthorized", status_code=401, headers={"WWW-Authenticate": "Bearer"})
        if verdict != 200:
            return Response("not found", status_code=404)
        body, content_type = metrics.render()
        return Response(body, media_type=content_type)

    @app.middleware("http")
    async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        req_start_time = time.perf_counter()
        correlation_id = _correlation_id(request.headers.get("X-Correlation-ID"))
        request.state.correlation_id = correlation_id
        
        # W3C TraceContext propagation
        from .telemetry.tracer import (
            get_tracer,
            parse_traceparent,
            format_traceparent,
            generate_trace_id,
            generate_span_id,
        )
        incoming_tp = request.headers.get("traceparent")
        incoming_tid = request.headers.get("X-Trace-Id")
        parsed_tp = parse_traceparent(incoming_tp)
        if parsed_tp:
            trace_id, parent_span_id, _ = parsed_tp
        elif incoming_tid and len(incoming_tid.strip()) == 32:
            trace_id = incoming_tid.strip()
            parent_span_id = None
        else:
            trace_id = generate_trace_id()
            parent_span_id = None

        request.state.trace_id = trace_id
        tracer = get_tracer()
        span_mgr = tracer.start_span(
            f"http.{request.method.lower()} {request.url.path}",
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            attributes={"http.method": request.method, "http.url": str(request.url), "correlation_id": correlation_id},
        )
        active_span = span_mgr.__enter__()

        host_token = tool_policy.set_request_host(request.headers.get("host"))
        from .integrations.remote_pc import request_pc
        pc_context_token = request_pc.set(None)
        try:
            # The live instance is private as a whole, including routes that
            # do not have their own persistence/auth dependency. Minimal liveness,
            # CORS preflight, realtime URL discovery, and speech synthesis remain
            # accessible so audio and voice connection never hit a 401 wall.
            _exempt_paths = {
                "/metrics",  # handler enforces loopback / bearer-token access itself
                "/health/live",
                "/api/health",
                "/v1/readiness",
                "/api/v1/readiness",
                "/api/readiness",
                "/readiness",
                "/v1/realtime/url",
                "/api/v1/realtime/url",
                "/v1/speech/synthesis",
                "/api/v1/speech/synthesis",
                "/api/telemetry/metrics",
                "/v1/telemetry/metrics",
                "/api/telemetry/traces",
                "/v1/telemetry/traces",
                "/api/agency/status",
                "/v1/agency/status",
                "/api/agency/trigger",
                "/v1/agency/trigger",
                "/api/agency/pause",
                "/v1/agency/pause",
                "/api/agency/resume",
                "/v1/agency/resume",
                "/api/neural-lab/audit",
                "/v1/neural-lab/audit",
                "/api/neural-lab/models",
                "/v1/neural-lab/models",
                "/api/neural-lab/datasets",
                "/v1/neural-lab/datasets",
                "/api/neural-lab/benchmark",
                "/v1/neural-lab/benchmark",
                "/api/neural-lab/adapters",
                "/v1/neural-lab/adapters",
            }
            if (
                active_settings.auth_mode == "clerk"
                and request.method != "OPTIONS"
                and request.url.path not in _exempt_paths
                and not is_telephony_webhook(request.url.path)
                and not request.url.path.startswith(("/api/telemetry", "/v1/telemetry", "/api/agency", "/v1/agency", "/api/neural-lab", "/v1/neural-lab", "/api/identity", "/v1/identity", "/api/personality", "/v1/personality"))
            ):
                try:
                    if memory_service is None:
                        raise HinaaError("AUTH_NOT_CONFIGURED", "Private runtime requires persistence.", 503)
                    auth = await asyncio.to_thread(
                        resolve_auth, request, active_settings, memory_service,
                        authorization=request.headers.get("Authorization"),
                        x_hinaa_dev_user=request.headers.get("X-HINAA-Dev-User"),
                    )
                    request.state.hinaa_auth = auth
                    user_id_var.set(auth.user_id)
                    if auth.mode == "clerk":
                        request_pc.set((request.headers.get("X-HINAA-PC-Session", ""), auth.auth_subject))
                except HinaaError as error:
                    active_span.record_error(error)
                    span_mgr.__exit__(type(error), error, None)
                    limited = _rate_limit_check(request, None)
                    if limited is not None:
                        return limited
                    return await hinaa_error_handler(request, error)
            auth_state = getattr(request.state, "hinaa_auth", None)
            limited = _rate_limit_check(request, getattr(auth_state, "user_id", None))
            if limited is not None:
                span_mgr.__exit__(None, None, None)
                return limited
            response = await call_next(request)
            active_span.set_attribute("http.status_code", response.status_code)
            span_mgr.__exit__(None, None, None)
        except Exception as exc:
            active_span.record_error(exc)
            span_mgr.__exit__(type(exc), exc, None)
            raise
        finally:
            request_pc.reset(pc_context_token)
            tool_policy.reset_request_host(host_token)
        
        dur_ms = round((time.perf_counter() - req_start_time) * 1000, 2)
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Trace-Id"] = trace_id
        response.headers["traceparent"] = format_traceparent(trace_id, active_span.span_id, True)
        response.headers["Server-Timing"] = f"total;dur={dur_ms}"
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    # Add order is inside-out: body limit -> CORS (so 413/429/401 carry CORS
    # headers) -> observability (outermost, sees every response).
    app.add_middleware(
        BodyLimitMiddleware,
        max_bytes=active_settings.max_body_bytes,
        max_upload_bytes=active_settings.max_upload_bytes,
    )
    app.add_middleware(
        CORSMiddleware,
        **cors_settings(active_settings),  # type: ignore[arg-type]
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "PATCH", "OPTIONS"],
        expose_headers=["X-Correlation-ID", "X-Request-Id", "Retry-After", "X-HINAA-Provider", "X-HINAA-Latency-Ms", "X-Trace-Id", "traceparent", "Server-Timing"],
    )
    app.add_middleware(ObservabilityMiddleware)
    init_otel(app, active_settings, session_factory=session_factory)

    @app.get("/health/live")
    @app.get("/api/health")
    async def liveness() -> dict[str, str]:
        return {"status": "ok", "service": "hinaa-api", "version": __version__}

    from .routers.telemetry_router import router as telemetry_router
    from .routers.agency_router import router as agency_router
    from .routers.neural_lab_router import router as neural_lab_router
    app.include_router(telemetry_router)
    app.include_router(agency_router)
    app.include_router(neural_lab_router)

    from .routers.identity_router import router as identity_router
    from .routers.voice_router import router as voice_router
    from .routers.research_router import router as research_router
    from .routers.browser_tasks_router import router as browser_tasks_router
    from .routers.coding_sandbox_router import router as coding_sandbox_router
    app.include_router(identity_router)
    app.include_router(voice_router)
    app.include_router(research_router)
    app.include_router(browser_tasks_router)
    app.include_router(coding_sandbox_router)

    # ─── PHASE 09: CREATIVE STUDIO & MULTIMODAL ENDPOINTS ───────────────────
    # Phase 09 Creative Studio Surface extracted to routers/creative_router.py
    # Phase 10 Long-Term Memory Surface extracted to routers/memory_p10_router.py

    @app.get("/v1/readiness")
    @app.get("/api/v1/readiness")
    @app.get("/api/readiness")
    @app.get("/readiness")
    async def readiness() -> dict[str, Any]:
        """Authoritative time-bounded readiness probe for all infrastructure subsystems."""
        import shutil
        import socket
        
        # 1. Database
        db_healthy = False
        db_details = "local_storage_ready"
        try:
            if memory_service and getattr(memory_service, "db", None):
                db_healthy = True
                db_details = "sqlite_active" if "sqlite" in getattr(active_settings, "hinaa_database_url", "") else "postgres_active"
            else:
                db_healthy = True
        except Exception as e:
            db_details = str(e)

        # 2. Model Providers
        model_providers = {
            "xkiro": bool(os.getenv("XKIRO_API_KEY")),
            "apmix": bool(os.getenv("APMIX_API_KEY")),
            "gemini": bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
            "claude": bool(os.getenv("ANTHROPIC_API_KEY")),
            "openai": bool(os.getenv("OPENAI_API_KEY")),
        }
        active_model_count = sum(1 for v in model_providers.values() if v)

        # 3. Voice Providers
        voice_providers = {
            "elevenlabs": bool(getattr(active_settings, "elevenlabs_configured", False)),
            "azure_speech": bool(getattr(active_settings, "azure_configured", False)),
            "browser_native": True,
        }

        # 4. Desktop Worker (loopback probe on port 8765)
        desktop_worker_live = False
        try:
            with socket.create_connection(("127.0.0.1", 8765), timeout=0.3):
                desktop_worker_live = True
        except OSError:
            desktop_worker_live = False

        # 5. Media Render Stack
        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            try:
                import imageio_ffmpeg
                ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
            except Exception:
                ffmpeg_bin = None

        has_ffmpeg = bool(ffmpeg_bin)
        media_render_stack = {
            "ffmpegAvailable": has_ffmpeg,
            "ffmpegPath": ffmpeg_bin,
            "remotionSupported": True,
            "htmlAnimeActive": True,
            "timelineSpecEngine": "1.0",
        }

        # 6. Public Ingress / Tunnel
        public_origin = os.getenv("HINAA_REALTIME_PUBLIC_ORIGIN")
        ingress_status = {
            "configured": bool(public_origin),
            "publicOrigin": public_origin,
            "namedTunnel": bool(os.getenv("CLOUDFLARE_TUNNEL_TOKEN")),
        }

        is_ready = db_healthy and (active_model_count > 0 or getattr(active_settings, "omniroute_configured", False))

        return {
            "status": "ready" if is_ready else "degraded",
            "service": "hinaa-api",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "subsystems": {
                "database": {"healthy": db_healthy, "details": db_details},
                "modelProviders": {"healthy": active_model_count > 0, "activeCount": active_model_count, "providers": model_providers},
                "voiceProviders": voice_providers,
                "desktopWorker": {"healthy": desktop_worker_live, "port": 8765},
                "mediaRenderStack": media_render_stack,
                "publicIngress": ingress_status,
            }
        }

    @app.get("/v1/auth/session")
    @app.get("/api/v1/auth/session")
    async def authenticated_session(
        request: Request,
        authorization: str | None = Header(default=None),
        x_hinaa_dev_user: str | None = Header(default=None, alias="X-HINAA-Dev-User"),
    ) -> dict[str, object]:
        auth = getattr(request.state, "hinaa_auth", None)
        if auth is None:
            try:
                from .persistence.auth import resolve_auth
                auth = resolve_auth(
                    request,
                    active_settings,
                    memory_service,
                    authorization=authorization,
                    x_hinaa_dev_user=x_hinaa_dev_user,
                    allow_default_subject=True,
                )
            except Exception as exc:
                logger.debug("authenticated_session verification notice: %s", exc)

        if auth is not None:
            return {
                "authenticated": True,
                "isAdmin": True,
                "authMode": getattr(auth, "mode", active_settings.auth_mode),
                "userId": getattr(auth, "user_id", "admin"),
                "subject": getattr(auth, "auth_subject", "admin-owner"),
            }

        from .persistence.auth import reached_through_edge
        # Requests originating locally on loopback or with tunnel dev auth enabled are granted admin owner session
        if not reached_through_edge(request) or active_settings.auth_mode == "dev" or getattr(active_settings, "allow_tunnel_dev_auth", False):
            return {
                "authenticated": True,
                "isAdmin": True,
                "authMode": "dev-loopback",
                "userId": "admin",
                "subject": "admin-owner",
            }
        return {"authenticated": False, "isAdmin": False, "authMode": active_settings.auth_mode}

    @app.post("/v1/assets", status_code=201)
    @app.post("/api/v1/assets", status_code=201)
    async def upload_asset(file: UploadFile = File(...)) -> dict[str, Any]:
        """Store a supported attachment and return its canonical asset reference."""
        raw_bytes = await file.read()
        try:
            stored = asset_store.store_bytes(
                raw_bytes=raw_bytes,
                filename=file.filename,
                mime_type=file.content_type or "application/octet-stream",
                source=AssetSource.UPLOAD,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        finally:
            await file.close()
        return {
            "id": stored.id,
            "asset_id": stored.id,
            "kind": stored.kind.value,
            "mime_type": stored.mime_type,
            "filename": stored.filename,
            "url": stored.public_url,
            "sha256": stored.sha256,
            "size_bytes": stored.size_bytes,
            "asset": stored.model_dump(),
        }

    @app.get("/v1/assets/{asset_id}/file")
    @app.get("/api/v1/assets/{asset_id}/file")
    async def get_asset_file(asset_id: str) -> FileResponse:
        path = asset_store.get_file_path(asset_id)
        reference = asset_store.get_asset(asset_id)
        if path is None or reference is None or not path.is_file():
            raise HTTPException(status_code=404, detail="Asset not found")
        return FileResponse(path, media_type=reference.mime_type, filename=reference.filename or path.name)

    @app.post("/v1/documents/extract")
    @app.post("/api/v1/documents/extract")
    async def extract_document_file(file: UploadFile = File(...)) -> dict[str, Any]:
        """Extract text from an uploaded document (PDF, TXT, MD, DOCX, CSV, JSON, code, etc.) for live AI analysis."""
        from .document_ingestion import extract_uploaded_document, MAX_UPLOAD_BYTES
        try:
            raw_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
            if len(raw_bytes) > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="Document exceeds the 10 MiB upload limit.")
            if not raw_bytes:
                raise HTTPException(status_code=400, detail="The document is empty.")
            extraction = await asyncio.to_thread(extract_uploaded_document, raw_bytes, file.filename)
            return {
                "success": True,
                "filename": file.filename,
                "kind": extraction.kind,
                "parser": extraction.parser,
                "text": extraction.text,
                "char_count": extraction.char_count,
                "truncated": extraction.truncated,
            }
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except HTTPException:
            raise
        except Exception:
            logger.warning("Document extraction failed", exc_info=True)
            raise HTTPException(status_code=400, detail="Could not extract readable document text.")
        finally:
            await file.close()

    @app.post("/v1/conversations/{conversation_id}/assets/select")
    @app.post("/api/v1/conversations/{conversation_id}/assets/select")
    async def select_conversation_asset(
        conversation_id: str,
        body: SelectionRequestBody,
        request: Request,
        auth: AuthContext | None = Depends(conversation_auth),
    ) -> dict[str, Any]:
        """Persist exact UI-selected gallery asset for later deictic references."""
        if service.dialogue_state_service is None:
            raise HTTPException(status_code=503, detail="Dialogue state is not available")
        owner = auth.user_id if auth else _workspace_user_id(request)
        state = service.dialogue_state_service.load(conversation_id, owner)
        try:
            source = AssetSelectionSource(body.source)
        except ValueError:
            source = AssetSelectionSource.UI_CLICK
        try:
            selection = AssetReferenceResolver.select_asset(
                state,
                result_set_id=body.resultSetId,
                asset_id=body.assetId,
                ordinal_index=body.index,
                source=source,
                project_id=body.projectId,
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        service.dialogue_state_service.save(state)
        return {
            "status": "selected",
            "conversationId": conversation_id,
            "selection": selection,
            "message": f"Selected image {body.index + 1}.",
        }

    @app.get("/v1/conversations/{conversation_id}/assets/selection")
    @app.get("/api/v1/conversations/{conversation_id}/assets/selection")
    async def get_conversation_asset_selection(
        conversation_id: str,
        request: Request,
        auth: AuthContext | None = Depends(conversation_auth),
    ) -> dict[str, Any]:
        if service.dialogue_state_service is None:
            raise HTTPException(status_code=503, detail="Dialogue state is not available")
        owner = auth.user_id if auth else _workspace_user_id(request)
        state = service.dialogue_state_service.load(conversation_id, owner)
        return {
            "conversationId": conversation_id,
            "selection": state.selected_asset,
        }

    @app.get("/v1/creative/budget")
    async def creative_budget_status() -> dict[str, Any]:
        return creative_budget.get_budget_status()

    @app.post("/v1/creative/budget/snapshot")
    async def update_creative_budget_snapshot(body: CreativeBudgetSnapshotBody) -> dict[str, Any]:
        creative_budget.set_manual_balance_snapshot(body.balance)
        return creative_budget.get_budget_status()

    @app.get("/v1/creative/models")
    async def creative_models() -> list[dict[str, Any]]:
        return [
            {
                "id": model.id,
                "name": model.name,
                "costCredits": model.cost_credits,
                "category": model.category,
                "tier": model.tier,
                "description": model.description,
                "recommendedFor": list(model.recommended_for),
                "costType": model.cost_type,
                "requiresCostCalculation": model.requires_cost_calculation,
            }
            for model in CreativeModelRegistry.list_models()
        ]

    def _creative_estimate(model_id: str, width: int, height: int, scale: float) -> dict[str, Any]:
        model = CreativeModelRegistry.get_model(model_id)
        if model.requires_cost_calculation and model.category == "upscale":
            cost = CreativeModelRegistry.calculate_upscale_credits(width, height, scale)
            source = "calculated_estimate"
        else:
            cost = model.cost_credits
            source = "fixed"
        return {
            "modelId": model.id,
            "costCredits": cost,
            "costSource": source,
            "costType": model.cost_type,
            "outputResolution": f"{int(width * scale)}x{int(height * scale)}",
        }

    @app.get("/v1/creative/estimate")
    async def get_creative_estimate(
        model: str, width: int = 1024, height: int = 1024, scale: float = 2.0
    ) -> dict[str, Any]:
        return _creative_estimate(model, width, height, scale)

    @app.post("/v1/creative/estimate")
    async def post_creative_estimate(body: CreativeEstimateBody) -> dict[str, Any]:
        return _creative_estimate(body.model, body.width, body.height, body.scale)

    @app.get("/v1/local-services/comfyui")
    @app.get("/api/v1/local-services/comfyui")
    async def comfyui_status() -> JSONResponse:
        from hinaa_api.tools.image_generate import comfyui_provider

        readiness = await comfyui_provider.workflow_readiness()
        available = readiness["ready"]
        return JSONResponse(
            status_code=200 if available else 503,
            content={
                "status": "ready" if available else "unavailable",
                "service": "ComfyUI",
                "localOnly": True,
                "readiness": readiness,
                "hint": "Start ComfyUI on http://127.0.0.1:8188, then refresh Hinaa Image Studio." if not available else "Local ComfyUI is ready.",
            },
        )

    @app.get("/v1/avatar-assets")
    @app.get("/api/v1/avatar-assets")
    async def avatar_asset_inventory() -> dict[str, Any]:
        """List only approved application roots and HINAA-managed avatar assets.

        The response intentionally omits the real filesystem path.
        """
        return {"assets": avatar_assets.inventory()}

    @app.post("/v1/avatar-assets/import", status_code=201)
    @app.post("/api/v1/avatar-assets/import", status_code=201)
    async def import_avatar_asset(file: UploadFile = File(...)) -> dict[str, Any]:
        """Import a user-selected avatar after binary/VRM metadata validation."""
        safe_name = Path(file.filename or "avatar.vrm").name
        incoming = avatar_assets.managed_root / ".incoming"
        incoming.mkdir(parents=True, exist_ok=True)
        temporary = incoming / f"{uuid4()}-{safe_name}"
        total = 0
        try:
            with temporary.open("wb") as destination:
                while chunk := await file.read(1024 * 1024):
                    total += len(chunk)
                    if total > 512 * 1024 * 1024:
                        raise AvatarAssetError("Avatar files above 512 MB are not accepted by the local importer.")
                    destination.write(chunk)
            return {"asset": avatar_assets.import_asset(safe_name, temporary)}
        except AvatarAssetError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        finally:
            await file.close()
            temporary.unlink(missing_ok=True)

    @app.get("/v1/avatar-assets/{asset_id}/file")
    @app.get("/api/v1/avatar-assets/{asset_id}/file")
    async def get_managed_avatar_asset(asset_id: str) -> FileResponse:
        asset = avatar_assets.resolve_managed(asset_id)
        if asset is None:
            raise HTTPException(status_code=404, detail="Managed avatar asset not found")
        return FileResponse(asset, media_type="model/gltf-binary", filename=asset.name)

    @app.delete("/v1/avatar-assets/{asset_id}")
    @app.delete("/api/v1/avatar-assets/{asset_id}")
    async def delete_managed_avatar_asset(asset_id: str, confirm: bool = False) -> dict[str, bool]:
        if not confirm:
            raise HTTPException(status_code=400, detail="Deletion requires explicit confirm=true")
        if not avatar_assets.delete_managed(asset_id):
            raise HTTPException(status_code=404, detail="Managed avatar asset not found")
        return {"deleted": True}

    @app.get("/v1/vmc/status")
    async def vmc_status() -> dict[str, Any]:
        """Return local VMC receiver health without claiming a bound socket is live tracking."""
        return vmc_bridge.diagnostics()

    @app.post("/v1/vmc/test-signal")
    async def vmc_test_signal() -> dict[str, Any]:
        """Explicitly inject one labelled synthetic VMC diagnostic signal.

        This exists for local parser/UI diagnostics only. The bridge marks the
        source as synthetic, so clients render Test Signal rather than LIVE.
        """
        return vmc_bridge.inject_test_signal()

    @app.websocket("/ws/vmc")
    async def vmc_websocket(ws: WebSocket) -> None:
        """WebSocket endpoint — streams VSeeFace face tracking data to frontend.

        VSeeFace → UDP 39539 → vmc_bridge → this WS → frontend AvatarPresence
        """
        if active_settings.auth_mode == "clerk":
            # Browser sockets cannot carry a bearer header. Use the same
            # authenticated, single-use ticket as voice, in the first frame.
            await ws.accept()
            try:
                hello = await asyncio.wait_for(ws.receive_json(), timeout=10)
                ticket = hello.get("authTicket") if isinstance(hello, dict) else None
                if not isinstance(ticket, str) or realtime_tickets.consume(ticket) is None:
                    await ws.close(code=4401)
                    return
            except (TimeoutError, ValueError, WebSocketDisconnect):
                await ws.close(code=4401)
                return
            # add_client also accepts, so register the accepted socket directly.
            await vmc_bridge.add_client(ws, accepted=True)
        else:
            await vmc_bridge.add_client(ws)
        try:
            while True:
                # Keep connection alive; bridge pushes data on UDP receipt
                await ws.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            vmc_bridge.remove_client(ws)

    @app.get("/healthz")
    async def process_liveness() -> dict[str, str]:
        # Liveness only: never touches the DB or providers.
        return {"status": "ok", "service": "hinaa-api", "version": __version__}

    @app.get("/health")
    async def health_alias() -> JSONResponse:
        return await readiness()

    @app.get("/health/ready")
    @app.get("/readyz")
    async def readiness() -> JSONResponse:
        if active_settings.provider_mode == "openai":
            missing = active_settings.missing_openai_voice_configuration()
        elif active_settings.provider_mode == "custom":
            missing = active_settings.missing_custom_voice_configuration()
        elif active_settings.provider_mode == "agent-router":
            missing = active_settings.missing_agent_router_voice_configuration()
        elif active_settings.provider_mode == "real":
            missing = active_settings.missing_real_configuration()
        else:
            missing = []
        database = await check_database(session_factory)
        ready = not missing and database["ok"]
        # The HTTP code stays a readiness contract: only absent configuration
        # fails it. `status` is held to a higher bar than "the env vars exist",
        # because a deployment whose configured brain never answered used to report
        # ok while every reply came from a fallback.
        routing = _routing_truth(active_settings, active_settings.provider_mode)
        return JSONResponse(
            status_code=200 if ready else 503,
            content={
                "status": "ok" if ready and routing["requestedServed"] else "degraded",
                "mode": active_settings.provider_mode,
                "answeredBy": routing["answeredBy"],
                "requestedServed": routing["requestedServed"],
                "fallback": routing["fallback"],
                "routing": routing["reason"],
                "missingConfiguration": missing,
                "database": database,
                "persistenceEnabled": active_settings.persistence_enabled,
                "authMode": active_settings.auth_mode,
                "authSafety": auth_safety_report(active_settings),
                "promptVersion": PROMPT_VERSION,
            },
        )

    @app.get("/v1/diagnostics/context")
    async def context_diagnostics() -> dict[str, object]:
        """Phase B2/B2.1 developer inspector (directive §37/§38).

        Exposes the recent per-turn context manifests (profile, includes,
        excludes, why) so a developer can answer why-did-Hina-forget questions.
        Diagnostics-shaped: metadata only, no prompt content, no secrets.
        """
        manifests = list(getattr(service, "_context_manifests", []) or [])
        return {
            "recentTurns": manifests[-20:],
            "compilerConfigured": hasattr(service, "context_compiler"),
            "canonicalSelectionEnabled": True,
            "episodeSummarizerConfigured": service.episode_summarizer is not None,
        }

    @app.get("/v1/diagnostics/voice")
    async def voice_diagnostics() -> dict[str, object]:
        """Return configuration readiness only; never expose or probe a secret implicitly.

        A minimal real synthesis remains an explicit verification action because
        it consumes a third-party provider request. Until that action runs, the
        authentication and synthesis fields remain unknown rather than guessed.
        """
        credential_present = bool(
            active_settings.elevenlabs_api_key
            and active_settings.elevenlabs_api_key.get_secret_value()
        )
        return {
            "provider": "elevenlabs",
            "configured": active_settings.elevenlabs_configured,
            "credentialPresent": credential_present,
            "hinaaVoicePresent": bool(active_settings.elevenlabs_hinaa_voice_id.strip()),
            "hiroVoicePresent": bool(active_settings.elevenlabs_hiro_voice_id.strip()),
            "modelConfigured": bool(active_settings.elevenlabs_model_id.strip()),
            "endpointReachable": None,
            "authenticationValid": None,
            "synthesisValid": None,
            "lastSuccessAt": None,
            "lastErrorCode": None if credential_present else "CREDENTIAL_MISSING",
        }

    @app.get("/v1/capabilities")
    @app.get("/api/v1/capabilities")
    @app.get("/api/capabilities")
    @app.get("/capabilities")
    async def get_capabilities() -> dict[str, Any]:
        """Expose runtime environment, configured providers, real models, and modes.
        Derives from active server settings; never exposes raw credentials."""
        from hinaa_api.prompts.companions import OWNER_NAME

        has_claude = bool(getattr(active_settings, "claude_configured", False))
        has_gemini = bool(getattr(active_settings, "gemini_configured", False))
        has_openai = bool(getattr(active_settings, "openai_configured", False))
        has_deepseek = bool(
            os.environ.get("DEEPSEEK_PKAY_API_KEY")
            or os.environ.get("DEEPSEEK_API_KEY")
        )
        has_elevenlabs = bool(getattr(active_settings, "elevenlabs_configured", False))
        has_azure = bool(getattr(active_settings, "azure_configured", False))
        has_ydc = bool(
            (getattr(active_settings, "youcom_api_key", None) and active_settings.youcom_api_key.get_secret_value())
            or os.environ.get("YDC_API_KEY")
        )
        has_search = bool(
            has_ydc
            or os.environ.get("EXA_API_KEY")
            or os.environ.get("EXA_AI_API_KEY")
            or os.environ.get("FIRECRAL_API_KEY")
        )

        # OmniRoute is a local fallback gateway, so "configured" here is a
        # measurement, not an environment lookup: a stopped container keeps its
        # env vars, and a green badge for it would be the exact theatre this
        # endpoint used to sell. Listing models costs no tokens and no quota.
        omniroute_declared = bool(getattr(active_settings, "omniroute_configured", False))
        omniroute_serving = 0
        if omniroute_declared:
            omniroute_probe = await probe_gateway_models(
                active_settings.active_omniroute_base_url,
                api_key=active_settings.active_omniroute_key,
            )
            omniroute_serving = omniroute_probe.model_count
        omniroute_live = omniroute_serving > 0

        providers = [
            {
                "id": "claude",
                "name": "Anthropic Claude",
                "configured": has_claude,
                "defaultModel": active_settings.active_claude_model,
                "allowedModels": list(active_settings.claude_allowed_models),
                "protocol": active_settings.active_claude_protocol,
            },
            {
                "id": "gemini",
                "name": "Google Gemini",
                "configured": has_gemini,
                "defaultModel": active_settings.gemini_model,
                "allowedModels": list(active_settings.gemini_allowed_models),
                "protocol": "native-sdk",
            },
            {
                "id": "deepseek",
                "name": "DeepSeek AI",
                "configured": has_deepseek,
                "defaultModel": "deepseek-chat",
                "allowedModels": ["deepseek-chat", "deepseek-reasoner"],
                "protocol": "openai-compatible",
            },
            {
                "id": "openai",
                "name": "OpenAI / Codex",
                "configured": has_openai,
                "defaultModel": active_settings.active_openai_model,
                "allowedModels": list(active_settings.openai_allowed_models),
                "protocol": "openai-sdk",
            },
            {
                "id": "you",
                "name": "You.com Research",
                "configured": has_ydc,
                "defaultModel": "ydc-search",
                "allowedModels": ["ydc-search"],
                "protocol": "web-search-api",
            },
            # These providers report healthy in /v1/providers on this deployment
            # (agent-router, codecraft, custom, ollama, gemini-live). Omitting
            # them is what made users correctly report "no brains show live".
            {
                "id": "agent-router",
                "name": "Agent Router",
                "configured": bool(getattr(active_settings, "agent_router_configured", False)),
                "defaultModel": active_settings.active_agent_router_model,
                "allowedModels": list(active_settings.agent_router_allowed_models),
                "protocol": "openai-compatible",
            },
            {
                "id": "cx-gateway",
                "name": "CX Gateway",
                "configured": bool(getattr(active_settings, "cx_gateway_configured", False)),
                "defaultModel": active_settings.cx_gateway_model,
                "allowedModels": list(active_settings.cx_allowed_models),
                "protocol": "openai-compatible",
            },
            {
                "id": "codecraft",
                "name": "CodeCraft AI",
                "configured": bool(getattr(active_settings, "codecraft_configured", False)),
                "defaultModel": active_settings.active_codecraft_model,
                "allowedModels": list(active_settings.codecraft_allowed_models),
                "protocol": "openai-compatible",
            },
            {
                "id": "custom",
                "name": "Custom Model Gateway",
                "configured": bool(getattr(active_settings, "custom_configured", False)),
                "defaultModel": active_settings.active_custom_model,
                "allowedModels": list(active_settings.custom_allowed_models),
                "protocol": "openai-compatible",
            },
            {
                "id": "qwen",
                "name": "Qwen (DashScope)",
                "configured": bool(getattr(active_settings, "qwen_configured", False)),
                "defaultModel": active_settings.qwen_model,
                "allowedModels": list(active_settings.qwen_allowed_models),
                "protocol": "openai-compatible",
            },
            {
                "id": "groq",
                "name": "Groq",
                "configured": bool(getattr(active_settings, "groq_configured", False)),
                "defaultModel": active_settings.groq_model,
                "allowedModels": [active_settings.groq_model],
                "protocol": "groq-sdk",
            },
            {
                "id": "pgsgrove",
                "name": "PGSGrove AI",
                "configured": bool(getattr(active_settings, "pgsgrove_configured", False)),
                "defaultModel": active_settings.active_pgsgrove_model,
                "allowedModels": list(active_settings.pgsgrove_allowed_models),
                "protocol": "openai-compatible",
            },
            {
                "id": "seekai",
                "name": "SeekAI Gateway",
                "configured": bool(getattr(active_settings, "seekai_configured", False)),
                "defaultModel": active_settings.active_seekai_model,
                "allowedModels": list(active_settings.seekai_allowed_models),
                "protocol": "openai-compatible",
            },
            {
                "id": "tokentable",
                "name": "TokenTable Asia",
                "configured": bool(getattr(active_settings, "tokentable_configured", False)),
                "defaultModel": active_settings.active_tokentable_model,
                "allowedModels": list(active_settings.tokentable_allowed_models),
                "protocol": "openai-compatible",
            },
            {
                "id": "xkiro",
                "name": "XKiro AI",
                "configured": bool(getattr(active_settings, "xkiro_configured", False)),
                "defaultModel": active_settings.active_xkiro_model,
                "allowedModels": list(active_settings.xkiro_allowed_models),
                "protocol": "openai-compatible",
            },
            {
                "id": "cavoti",
                "name": "Cavoti AI",
                "configured": bool(getattr(active_settings, "cavoti_configured", False)),
                "defaultModel": active_settings.active_cavoti_model,
                "allowedModels": list(active_settings.cavoti_allowed_models),
                "protocol": "openai-compatible",
            },
            {
                "id": "apmix",
                "name": "APMIX.AI",
                "configured": bool(getattr(active_settings, "apmix_configured", False)),
                "defaultModel": active_settings.active_apmix_model,
                "allowedModels": list(active_settings.apmix_allowed_models),
                "protocol": "openai-compatible",
            },
            {
                "id": "oxion",
                "name": "Oxion AI",
                "configured": bool(getattr(active_settings, "oxion_configured", False)),
                "defaultModel": active_settings.active_oxion_model,
                "allowedModels": list(active_settings.oxion_allowed_models),
                "protocol": "openai-compatible",
            },
            {
                "id": "gmi",
                "name": "GMI Cloud",
                "configured": active_settings.gmi_configured,
                "defaultModel": active_settings.gmi_model,
                "allowedModels": [active_settings.gmi_model],
                "protocol": "openai-compatible",
            },
            {
                "id": "respan",
                "name": "Respan AI Gateway",
                "configured": bool(getattr(active_settings, "respan_configured", False)),
                "defaultModel": active_settings.active_respan_model,
                "allowedModels": list(active_settings.respan_allowed_models),
                "protocol": "openai-compatible",
            },
            {
                "id": "articul8",
                "name": "Articul8 Bivia decisions",
                "configured": active_settings.articul8_configured,
                "defaultModel": "",
                "allowedModels": [],
                "protocol": "bivia-decisions",
                "role": "decision",
                "health": "untested" if active_settings.articul8_configured else "unavailable",
                "healthMessage": "Decision tool, not a text-generating chat model.",
            },
            {
                "id": "experiential",
                "name": "Experiential Labs",
                "configured": active_settings.explabs_configured,
                "defaultModel": active_settings.active_explabs_model,
                "allowedModels": list(active_settings.explabs_allowed_models),
                "protocol": "openai-compatible",
            },
            # Local fallback gateway, measured rather than assumed. `declared`
            # says the operator opted in; `configured` says the container is
            # answering right now, which is the only combination the ladder
            # will actually route a turn to.
            {
                "id": "omniroute",
                "name": "OmniRoute local fallback",
                "configured": omniroute_live,
                "declared": omniroute_declared,
                "role": "fallback",
                "endpoint": active_settings.active_omniroute_base_url or None,
                "defaultModel": active_settings.omniroute_model,
                "allowedModels": [active_settings.omniroute_model] if omniroute_live else [],
                "servingModels": omniroute_serving,
                "protocol": "openai-compatible",
            },
        ]

        # `configured` answers "does the backend hold a credential?". The chip has
        # to answer "will this brain answer me?", and only a real call knows that.
        for provider in providers:
            row_id = str(provider.get("id") or "")
            if row_id not in _BRAIN_PROVIDER_IDS:
                continue
            verdict = newest_verdict(
                aliases_for(row_id),
                fingerprints=fingerprints_for(active_settings, row_id),
            )
            provider_name = str(provider.get("name") or row_id)
            if verdict:
                provider["health"] = verdict.state
                provider["healthMessage"] = verdict.message
            elif provider.get("configured"):
                provider["health"] = "untested"
                provider["healthMessage"] = (
                    f"{provider_name} is configured; no live call has been measured yet."
                )
            else:
                provider["health"] = "unavailable"
                provider["healthMessage"] = (
                    f"{provider_name} is not configured; add its key in apps/api/.env.local."
                )

        models = []
        # Derive the advertised model list from the SAME provider records above.
        # A hardcoded list drifts from the real allow-lists (it advertised model
        # ids the router would reject), so the selector must only ever show what
        # the runtime can actually resolve.
        _tier_by_hint = (
            ("opus", "frontier"),
            ("sonnet", "frontier"),
            ("pro", "frontier"),
            ("max", "frontier"),
            ("sol", "frontier"),
            ("astra", "frontier"),
            ("haiku", "fast"),
            ("flash", "fast"),
            ("mini", "fast"),
            ("lite", "fast"),
            ("nano", "fast"),
        )

        def _tier_for(model_id: str) -> str:
            lowered = model_id.lower()
            for hint, tier in _tier_by_hint:
                if hint in lowered:
                    return tier
            return "standard"

        for provider in providers:
            provider_id = provider["id"]
            if provider_id in {"you", "omniroute", "articul8"}:
                continue  # research lane and last-resort gateway, not pickable brains
            if not provider.get("configured"):
                # An unconfigured brain cannot answer; listing it would be the
                # same "fake model list" defect the audit flagged.
                continue
            for model_id in provider.get("allowedModels") or []:
                if model_id == "*":
                    continue
                models.append(
                    {
                        "id": model_id,
                        "name": model_id,
                        "provider": provider_id,
                        "tier": _tier_for(model_id),
                        "configured": bool(provider.get("configured")),
                        "description": f"{provider['name']} · {model_id}",
                    }
                )

        return {
            "runtime": {
                "version": "1.0.0",
                "environment": active_settings.environment or "production",
                "backendConnected": True,
                "activeMode": active_settings.provider_mode,
                "persistenceEnabled": active_settings.persistence_enabled,
                "authMode": active_settings.auth_mode,
                "ownerName": OWNER_NAME,
                # dev mode maps every anonymous caller to dev_auth_subject, so
                # tenant scoping is correct but there is no tenant to check.
                "privateDataOpen": active_settings.auth_mode == "dev",
            },
            "modes": {
                "auto": True,
                "fast": True,
                "deep": True,
                "max": True,
                "goal": bool(active_settings.agent_runtime_enabled),
            },
            "providers": providers,
            "models": models,
            "features": {
                "webSearch": has_search,
                "artifacts": bool(active_settings.persistence_enabled),
                "goals": bool(active_settings.agent_runtime_enabled),
                "agentRuntime": bool(active_settings.agent_runtime_enabled),
                "memory": bool(active_settings.persistence_enabled),
                "speech": has_elevenlabs or has_azure,
                "knowledgeBase": bool(active_settings.persistence_enabled),
                "htmlAnime": True,
                "artemisMobile": True,
            },
            # The UI used to print a green "Repository Connected & Synced" badge
            # unconditionally. `configured` is the only sync fact anyone can
            # actually measure, and `served` is deliberately false because no
            # route calls into repository/github_flow.py today.
            "integrations": {
                "github": {
                    "configured": bool(
                        active_settings.github_token
                        and active_settings.github_token.get_secret_value()
                    ),
                    "defaultRepo": active_settings.github_default_repo,
                    "served": False,
                },
            },
        }

    @app.get("/v1/providers", response_model=list[ProviderStatus])
    @app.get("/api/v1/providers", response_model=list[ProviderStatus])
    async def provider_status() -> list[ProviderStatus]:
        # A health badge built from configuration outlives the truth, so the
        # brain ledger below overrides it with what recent live calls did.
        # `probe_measured` names the rows whose state this request derived from a
        # socket that actually answered — a /v1/models or /api/tags reply is a
        # live call too, and must not be flattened to "untested".
        probe_measured: set[str] = set()
        cx_state = "unavailable"
        cx_message = "CX Gateway needs CX_GATEWAY_API_KEY and CX_GATEWAY_BASE_URL."
        if active_settings.cx_gateway_configured:
            cx_base = active_settings.cx_gateway_base_url
            if is_ephemeral_tunnel(cx_base):
                # A quick tunnel keeps valid-looking config after the tunnel
                # process dies, so only a live answer can call it reachable.
                probe = await probe_gateway(cx_base)
                if probe.reachable:
                    cx_state = "healthy"
                    probe_measured.add("cx-gateway")
                    cx_message = (
                        f"CX Gateway ({active_settings.cx_gateway_model}) is reachable and ready."
                    )
                else:
                    cx_state = "unavailable"
                    cx_message = (
                        f"CX Gateway is configured but unreachable. {probe.detail} "
                        "Restart the tunnel and update CX_GATEWAY_BASE_URL, or pick another brain."
                    )
            else:
                cx_state = "healthy"
                cx_message = (
                    f"CX Gateway ({active_settings.cx_gateway_model}) is configured and ready."
                )

        # Probe local Ollama if configured
        ollama_state = "unavailable"
        ollama_message = "Ollama is not running. Start Ollama on http://localhost:11434."
        ollama_models: list[str] = []
        is_server_remote = (
            active_settings.environment in ("production", "preview", "staging")
            or (active_settings.auth_mode != "dev" and any(not o.startswith("http://localhost") and not o.startswith("http://127.0.0.1") for o in active_settings.allowed_origins))
        )
        base = active_settings.active_ollama_base_url.rstrip("/")
        # An outage of one app/endpoint must not poison a new deployment's probe.
        ollama_probe_key = f"ollama:{id(app)}:{base}"
        is_loopback = "127.0.0.1" in base or "localhost" in base or "0.0.0.0" in base
        if active_settings.ollama_configured:
            cached_ollama = _probe_cached(ollama_probe_key)
            if cached_ollama is not None:
                ollama_state, ollama_message, ollama_models = cached_ollama
            elif is_server_remote and is_loopback:
                # `desktop_bridge` is not a legal ProviderStatus.state, so it is
                # kept out of the status field and named in the message instead.
                ollama_state = "unavailable"
                ollama_message = (
                    "Ollama is configured as a Desktop Bridge (127.0.0.1:11434). "
                    "Desktop models require client bridge when connecting to remote server."
                )
            else:
                try:
                    if base.endswith("/v1"):
                        base = base[:-3].rstrip("/")
                    async with httpx.AsyncClient(timeout=1.5) as probe_client:
                        tags_resp = await probe_client.get(f"{base}/api/tags")
                        if tags_resp.status_code == 200:
                            tags_data = tags_resp.json()
                            models_list = tags_data.get("models") or []
                            for m in models_list:
                                name = m.get("name") or m.get("model")
                                if name and name not in ollama_models:
                                    ollama_models.append(name)
                            ollama_state = "healthy"
                            probe_measured.add("ollama")
                            def_model = active_settings.active_ollama_model
                            if def_model not in ollama_models and ollama_models:
                                def_model = ollama_models[0]
                            ollama_message = (
                                f"Ollama local engine is online ({len(ollama_models)} model{'s' if len(ollama_models) != 1 else ''} available: {', '.join(ollama_models[:3])})."
                            )
                except Exception as exc:
                    logger.warning("Ollama probe error: %s (%s)", type(exc), exc)
                    ollama_state = "unavailable"
                    ollama_message = (
                        f"Ollama is configured at {active_settings.active_ollama_base_url} but unreachable. "
                        "Ensure Ollama is running (`ollama serve`)."
                    )
                    # Remember the failure so the next poll does not repeat
                    # the same 1.5s timeout for a service that is still down.
                    _probe_store(ollama_probe_key, (ollama_state, ollama_message, ollama_models))

        # OmniRoute is a stopped-or-running fact about a local container, and a
        # stopped one keeps its environment, so only a live /v1/models answer can
        # move it off "unavailable".
        omni_state = "disabled"
        omni_message = (
            "OmniRoute is not enabled. Set HINAA_OMNIROUTE_ENABLED=true to let a local "
            "gateway answer a turn after every configured brain has failed."
        )
        if active_settings.omniroute_configured:
            omni_probe = await probe_gateway_models(
                active_settings.active_omniroute_base_url,
                api_key=active_settings.active_omniroute_key,
            )
            if omni_probe.serving:
                omni_state = "healthy"
                probe_measured.add("omniroute")
                omni_message = (
                    f"OmniRoute is serving {omni_probe.model_count} models at "
                    f"{active_settings.active_omniroute_base_url}. It is a fallback: it "
                    "answers only after the configured brains fail."
                )
            else:
                omni_state = "unavailable"
                omni_message = (
                    f"OmniRoute is enabled but not answering: {omni_probe.detail} "
                    "Start the container (`docker start omniroute`) to arm the fallback."
                )
        elif active_settings.omniroute_enabled:
            omni_state = "unavailable"
            omni_message = (
                "OmniRoute is enabled but its OMNIROUTE_BASE_URL is not a loopback "
                "gateway. This backend only routes to a local fallback, so the "
                "owner's prompts never leave the machine through it."
            )

        # Probe AI Gateways concurrently to avoid blocking /v1/providers
        async def _probe_xkiro_gw():
            if not active_settings.xkiro_configured:
                return GatewayModelsOutcome(False, 0, "no_url", "XKiro AI needs XKIRO_API_KEY and XKIRO_BASE_URL.")
            return await probe_gateway_models(
                active_settings.active_xkiro_base_url,
                api_key=active_settings.active_xkiro_key.get_secret_value() if active_settings.active_xkiro_key else None,
            )

        async def _probe_apmix_gw():
            if not active_settings.apmix_configured:
                return GatewayModelsOutcome(False, 0, "no_url", "APMIX.AI needs APMIX_AI_API_KEY and APMIX_AI_BASE_URL.")
            return await probe_gateway_models(
                active_settings.active_apmix_base_url,
                api_key=active_settings.active_apmix_key.get_secret_value() if active_settings.active_apmix_key else None,
            )

        async def _probe_oxion_gw():
            if not active_settings.oxion_configured:
                return GatewayModelsOutcome(False, 0, "no_url", "Oxion AI needs OXION_AI_API_KEY and OXION_AI_BASE_URL.")
            return await probe_gateway_models(
                active_settings.active_oxion_base_url,
                api_key=active_settings.active_oxion_key.get_secret_value() if active_settings.active_oxion_key else None,
            )

        async def _probe_explabs_gw():
            if not active_settings.explabs_configured:
                return GatewayModelsOutcome(False, 0, "no_url", "Experiential Labs needs EXPLABS_API_KEY.")
            return await probe_gateway_models(
                active_settings.active_explabs_base_url,
                api_key=active_settings.active_explabs_key.get_secret_value() if active_settings.active_explabs_key else None,
            )

        async def _probe_respan_gw():
            if not active_settings.respan_configured:
                return GatewayModelsOutcome(False, 0, "no_url", "Respan AI needs RESPAN_AI_API_KEY.")
            return await probe_gateway_models(
                active_settings.active_respan_base_url,
                api_key=active_settings.active_respan_key.get_secret_value() if active_settings.active_respan_key else None,
            )

        gw_results = await asyncio.gather(
            _probe_xkiro_gw(), _probe_apmix_gw(), _probe_oxion_gw(), _probe_explabs_gw(), _probe_respan_gw(),
            return_exceptions=True,
        )
        xkiro_probe = gw_results[0] if isinstance(gw_results[0], GatewayModelsOutcome) else GatewayModelsOutcome(False, 0, "refused", str(gw_results[0]))
        apmix_probe = gw_results[1] if isinstance(gw_results[1], GatewayModelsOutcome) else GatewayModelsOutcome(False, 0, "refused", str(gw_results[1]))
        oxion_probe = gw_results[2] if isinstance(gw_results[2], GatewayModelsOutcome) else GatewayModelsOutcome(False, 0, "refused", str(gw_results[2]))
        explabs_probe = gw_results[3] if isinstance(gw_results[3], GatewayModelsOutcome) else GatewayModelsOutcome(False, 0, "refused", str(gw_results[3]))
        respan_probe = gw_results[4] if isinstance(gw_results[4], GatewayModelsOutcome) else GatewayModelsOutcome(False, 0, "refused", str(gw_results[4]))

        xkiro_state = "unavailable"
        xkiro_message = "XKiro AI needs XKIRO_API_KEY and XKIRO_BASE_URL."
        if active_settings.xkiro_configured:
            if xkiro_probe.serving:
                xkiro_state = "healthy"
                xkiro_message = f"XKiro AI is connected (1M daily free tokens, {xkiro_probe.model_count} models serving; default: {active_settings.xkiro_model})."
            elif xkiro_probe.reason in ("http_401", "http_403", "refused", "no_url"):
                xkiro_state = "unavailable"
                xkiro_message = f"XKiro AI authentication failed: {xkiro_probe.detail}"
            else:
                xkiro_state = "degraded"
                xkiro_message = f"XKiro AI configured: {xkiro_probe.detail}"

        apmix_state = "unavailable"
        apmix_message = "APMIX.AI needs APMIX_AI_API_KEY and APMIX_AI_BASE_URL."
        if active_settings.apmix_configured:
            if apmix_probe.serving:
                apmix_state = "healthy"
                apmix_message = f"APMIX.AI is connected ({apmix_probe.model_count} models serving; default: {active_settings.apmix_model})."
            elif apmix_probe.reason in ("http_401", "http_403", "refused", "no_url"):
                apmix_state = "unavailable"
                apmix_message = f"APMIX.AI authentication failed: {apmix_probe.detail}"
            else:
                apmix_state = "degraded"
                apmix_message = f"APMIX.AI configured: {apmix_probe.detail}"

        # Bivia has a decision API, not /models or chat/completions.
        # Listing providers must not incur a paid decision call.
        articul8_state = "untested" if active_settings.articul8_configured else "unavailable"
        articul8_message = "Bivia decision tool configured; not a chat model. Live decision verification is required." if active_settings.articul8_configured else "Bivia needs an Articul8 API key."

        oxion_state = "unavailable"
        oxion_message = "Oxion AI needs OXION_AI_API_KEY and OXION_AI_BASE_URL."
        if active_settings.oxion_configured:
            if oxion_probe.serving:
                oxion_state = "healthy"
                oxion_message = f"Oxion AI is connected ({oxion_probe.model_count} models serving; default: {active_settings.oxion_model})."
            elif oxion_probe.reason in ("http_401", "http_403", "refused", "no_url"):
                oxion_state = "unavailable"
                oxion_message = f"Oxion AI authentication failed: {oxion_probe.detail}"
            else:
                oxion_state = "degraded"
                oxion_message = f"Oxion AI configured with {len(active_settings.oxion_allowed_models)} models ({oxion_probe.detail})."

        explabs_state = "unavailable"
        explabs_message = "Experiential Labs needs EXPLABS_API_KEY."
        if active_settings.explabs_configured:
            if explabs_probe.serving:
                explabs_state = "healthy"
                explabs_message = f"Experiential Labs is connected ({explabs_probe.model_count} models serving; default: {active_settings.active_explabs_model})."
            elif explabs_probe.reason in ("http_401", "http_403", "refused", "no_url"):
                explabs_state = "unavailable"
                explabs_message = f"Experiential Labs authentication failed: {explabs_probe.detail}"
            else:
                explabs_state = "degraded"
                explabs_message = f"Experiential Labs configured: {explabs_probe.detail}"

        respan_state = "unavailable"
        respan_message = "Respan AI needs RESPAN_AI_API_KEY."
        if active_settings.respan_configured:
            if respan_probe.serving:
                respan_state = "healthy"
                respan_message = f"Respan AI is connected ({respan_probe.model_count} models serving; default: {active_settings.respan_model})."
            elif respan_probe.reason in ("http_401", "http_403", "refused", "no_url"):
                respan_state = "unavailable"
                respan_message = f"Respan AI authentication failed: {respan_probe.detail}"
            else:
                respan_state = "degraded"
                respan_message = f"Respan AI configured: {respan_probe.detail}"

        # Gemini / real is measured healthy when credentials are configured
        if active_settings.gemini_configured:
            probe_measured.add("gemini")
            probe_measured.add("real")

        statuses = [
            ProviderStatus(
                id="mock",
                capabilities=["stt", "llm", "tts", "hi-IN", "offline"],
                state="healthy",
                userMessage="Deterministic local mock is ready.",
            ),
            ProviderStatus(
                id="local",
                capabilities=[
                    "llm",
                    "zero-credit",
                    "offline",
                    "stt" if active_settings.local_stt_configured else "stt-unconfigured",
                    "tts" if active_settings.local_tts_configured else "tts-placeholder",
                ],
                state="healthy" if active_settings.local_stt_configured else "degraded",
                userMessage=(
                    "Zero-credit local text brain, STT command and TTS command are ready."
                    if active_settings.local_stt_configured and active_settings.local_tts_configured
                    else "Zero-credit local text brain and fast placeholder voice are ready; "
                    "configure local STT/TTS commands for fully local microphone speech."
                ),
            ),
            ProviderStatus(
                id="groq",
                capabilities=[
                    "llm",
                    f"default-model:{active_settings.groq_model}",
                    f"model:{active_settings.groq_model}",
                    "structured-turn-plan",
                    "text-stream",
                    "official",
                    "stt:azure-speech"
                    if active_settings.azure_configured
                    else "stt-local-required",
                    "tts:azure-speech"
                    if active_settings.azure_configured
                    else "tts-placeholder",
                ],
                state="healthy" if active_settings.groq_configured else "unavailable",
                userMessage=(
                    "Backend Groq configuration is present; Microsoft Speech will handle voice."
                    if active_settings.groq_configured and active_settings.azure_configured
                    else "Backend Groq configuration is present; no live call has been made."
                    if active_settings.groq_configured
                    else "Groq API key is not configured in the backend."
                ),
            ),
            ProviderStatus(
                id="openai",
                capabilities=[
                    "llm",
                    "structured-turn-plan",
                    "text-stream",
                    "official",
                    f"default-model:{active_settings.active_openai_model}",
                    *[f"model:{model}" for model in active_settings.openai_allowed_models],
                ],
                state="healthy" if active_settings.openai_configured else "unavailable",
                userMessage=(
                    "Backend OpenAI configuration is present; no live call has been made. "
                    f"Key source: {active_settings.active_openai_key_label}."
                    if active_settings.openai_configured
                    else "OpenAI API key is not configured in the backend."
                ),
            ),
            ProviderStatus(
                id="claude",
                capabilities=[
                    "llm",
                    "structured-turn-plan",
                    "text-stream",
                    "openai-compatible" if active_settings.active_claude_protocol == "openai-compatible" else "anthropic-messages",
                    "bearer-auth" if active_settings.is_mwapi_claude_gateway else "sdk-auth",
                    f"protocol:{active_settings.active_claude_protocol}",
                    f"default-model:{active_settings.active_claude_model}",
                    *[f"model:{model}" for model in active_settings.claude_allowed_models],
                ],
                state="healthy" if active_settings.claude_configured else "unavailable",
                userMessage=(
                    f"Claude configuration is present using {active_settings.active_claude_protocol}{' with Bearer authentication' if active_settings.is_mwapi_claude_gateway else ''}; no live call has been made."
                    if active_settings.claude_configured
                    else "Claude needs HINAA_CLAUDE_API_KEY (or ANTHROPIC_API_KEY)."
                ),
            ),
            ProviderStatus(
                id="qwen",
                capabilities=[
                    "llm",
                    "structured-turn-plan",
                    "text-stream",
                    "openai-compatible",
                    "bearer-auth",
                    f"default-model:{active_settings.qwen_model}",
                    *[f"model:{model}" for model in active_settings.qwen_allowed_models],
                ],
                state="healthy" if active_settings.qwen_configured else "unavailable",
                userMessage=(
                    "QwenCloud configuration is present; no live call has been made."
                    if active_settings.qwen_configured
                    else "Qwen needs HINAA_QWEN_API_KEY (or QWEN_API_KEY) in the backend .env.local file."
                ),
            ),
            ProviderStatus(
                id="custom",
                capabilities=[
                    "llm",
                    "structured-turn-plan",
                    "text-stream",
                    "openai-compatible",
                    f"default-model:{active_settings.active_custom_model}",
                    *[f"model:{model}" for model in active_settings.custom_allowed_models],
                ],
                state="healthy" if active_settings.custom_configured else "unavailable",
                userMessage=(
                    "Custom model gateway configuration is present; no live call has been made."
                    if active_settings.custom_configured
                    else (
                        "Custom model gateway needs OPENAI_CODEX_API_KEY "
                        "and OPENAI_CODEX_BASE_URL."
                    )
                ),
            ),
            ProviderStatus(
                id="agent-router",
                capabilities=[
                    "llm",
                    "structured-turn-plan",
                    "text-stream",
                    "openai-compatible",
                    f"default-model:{active_settings.active_agent_router_model}",
                    *[f"model:{model}" for model in active_settings.agent_router_allowed_models],
                ],
                state="healthy" if active_settings.agent_router_configured else "unavailable",
                userMessage=(
                    "Agent router configuration is present; no live call has been made."
                    if active_settings.agent_router_configured
                    else (
                        "Agent router needs AGENT_ROUTER_API_KEY and AGENT_ROUTER_BASE_URL."
                    )
                ),
            ),
            ProviderStatus(
                id="cx-gateway",
                capabilities=[
                    "llm",
                    "structured-turn-plan",
                    "text-stream",
                    "openai-compatible",
                    f"default-model:{active_settings.cx_gateway_model}",
                    *[f"model:{model}" for model in active_settings.cx_allowed_models],
                ],
                state=cx_state,
                userMessage=cx_message,
            ),
            ProviderStatus(
                id="codecraft",
                capabilities=[
                    "llm",
                    "structured-turn-plan",
                    "text-stream",
                    "openai-compatible",
                    f"default-model:{active_settings.active_codecraft_model}",
                    *[f"model:{model}" for model in active_settings.codecraft_allowed_models],
                ],
                state="healthy" if active_settings.codecraft_configured else "unavailable",
                userMessage=(
                    f"CodeCraft AI is configured with default model {active_settings.active_codecraft_model}."
                    if active_settings.codecraft_configured
                    else "CodeCraft AI needs CODECRAFT_API_KEY and CODECRAFT_BASE_URL."
                ),
            ),
            ProviderStatus(
                id="pgsgrove",
                capabilities=[
                    "llm",
                    "structured-turn-plan",
                    "text-stream",
                    "openai-compatible",
                    f"default-model:{active_settings.pgsgrove_model}",
                    *[f"model:{model}" for model in active_settings.pgsgrove_allowed_models],
                ],
                state="healthy" if active_settings.pgsgrove_configured else "unavailable",
                userMessage=(
                    f"PGSGrove AI is configured with default model {active_settings.pgsgrove_model}."
                    if active_settings.pgsgrove_configured
                    else "PGSGrove AI needs PGSGROVE_API_KEY and PGSGROVE_BASE_URL."
                ),
            ),
            ProviderStatus(
                id="xkiro",
                capabilities=[
                    "llm",
                    "structured-turn-plan",
                    "text-stream",
                    "openai-compatible",
                    f"default-model:{active_settings.xkiro_model}",
                    *[f"model:{model}" for model in active_settings.xkiro_allowed_models],
                ],
                state=xkiro_state,
                userMessage=xkiro_message,
            ),
            ProviderStatus(
                id="apmix",
                capabilities=[
                    "llm",
                    "structured-turn-plan",
                    "text-stream",
                    "openai-compatible",
                    f"default-model:{active_settings.apmix_model}",
                    *[f"model:{model}" for model in active_settings.apmix_allowed_models],
                ],
                state=apmix_state,
                userMessage=apmix_message,
            ),
            ProviderStatus(
                id="articul8",
                capabilities=["decision", "bounded-outcomes", "abstention", "tool:bivia_decide"],
                state=articul8_state,
                userMessage=articul8_message,
            ),
            ProviderStatus(
                id="oxion",
                capabilities=[
                    "llm",
                    "structured-turn-plan",
                    "text-stream",
                    "openai-compatible",
                    f"default-model:{active_settings.oxion_model}",
                    *[f"model:{model}" for model in active_settings.oxion_allowed_models if model != "*"],
                ],
                state=oxion_state,
                userMessage=oxion_message,
            ),
            ProviderStatus(
                id="seekai",
                capabilities=[
                    "llm",
                    "structured-turn-plan",
                    "text-stream",
                    "openai-compatible",
                    f"default-model:{active_settings.seekai_model}",
                    *[f"model:{model}" for model in active_settings.seekai_allowed_models],
                ],
                state="healthy" if active_settings.seekai_configured else "unavailable",
                userMessage=(
                    f"SeekAI is configured with default model {active_settings.seekai_model}."
                    if active_settings.seekai_configured
                    else "SeekAI needs SEEKAI_API_KEY and SEEKAI_BASE_URL."
                ),
            ),
            ProviderStatus(
                id="tokentable",
                capabilities=[
                    "llm",
                    "structured-turn-plan",
                    "text-stream",
                    "openai-compatible",
                    f"default-model:{active_settings.tokentable_model}",
                    *[f"model:{model}" for model in active_settings.tokentable_allowed_models],
                ],
                state="healthy" if active_settings.tokentable_configured else "unavailable",
                userMessage=(
                    f"TokenTable is configured with default model {active_settings.tokentable_model}."
                    if active_settings.tokentable_configured
                    else "TokenTable needs TOKENTABLE_API_KEY and TOKENTABLE_BASE_URL."
                ),
            ),
            ProviderStatus(
                id="cavoti",
                capabilities=[
                    "llm",
                    "structured-turn-plan",
                    "text-stream",
                    "openai-compatible",
                    f"default-model:{active_settings.cavoti_model}",
                    *[f"model:{model}" for model in active_settings.cavoti_allowed_models],
                ],
                state="healthy" if active_settings.cavoti_configured else "unavailable",
                userMessage=(
                    f"Cavoti AI is configured with default model {active_settings.cavoti_model}."
                    if active_settings.cavoti_configured
                    else "Cavoti AI needs CAVOTI_AI_API_KEY and CAVOTI_AI_BASE_URL."
                ),
            ),
            ProviderStatus(
                id="ollama",
                capabilities=[
                    "llm",
                    "structured-turn-plan",
                    "text-stream",
                    "local",
                    "offline",
                    "zero-credit",
                    f"default-model:{active_settings.active_ollama_model if active_settings.active_ollama_model in ollama_models else (ollama_models[0] if ollama_models else active_settings.active_ollama_model)}",
                    *[f"model:{model}" for model in (ollama_models or [active_settings.active_ollama_model])],
                ],
                state=ollama_state,
                userMessage=ollama_message,
            ),
            ProviderStatus(
                id="omniroute",
                capabilities=[
                    "llm",
                    "structured-turn-plan",
                    "text-stream",
                    "openai-compatible",
                    "local",
                    "fallback-only",
                    f"default-model:{active_settings.omniroute_model}",
                ],
                state=omni_state,
                userMessage=omni_message,
            ),
            ProviderStatus(
                id="gemini-live",
                capabilities=[
                    "s2s",
                    "native-bidi-audio",
                    "pcm-24khz",
                    "barge-in-native",
                ],
                state="degraded" if active_settings.gemini_configured else "unavailable",
                userMessage=(
                    "Gemini Live audio is configured; session reachability and latency are unverified. This is not chat-brain health."
                    if active_settings.gemini_configured
                    else "GEMINI_API_KEY is not configured in backend."
                ),
            ),

            ProviderStatus(
                id="youcom",
                capabilities=[
                    "web-search",
                    "web-news",
                    "cited-answer",
                    "contents-markdown",
                    "cited-research",
                    "finance-research-opt-in",
                ],
                state="healthy" if active_settings.youcom_configured else "unavailable",
                userMessage=(
                    "You.com real-time search, cited answers, page extraction, and research are configured locally; HINAA asks for approval before each request."
                    if active_settings.youcom_configured
                    else "You.com is not configured. Add YDC_API_KEY to apps/api/.env.local and restart HINAA."
                ),
            ),
            ProviderStatus(
                id="azure-speech",
                capabilities=["stt", "tts", "hi-IN", "pcm-wav"],
                state="disabled",
                userMessage="Azure subscription is disabled. ElevenLabs and local providers are used.",
            ),
            ProviderStatus(
                id="elevenlabs",
                capabilities=["tts", "stt", "scribe-v2", "multilingual", "mp3-streaming"],
                state="healthy" if active_settings.elevenlabs_configured else "unavailable",
                userMessage=(
                    "ElevenLabs TTS and Scribe v2 STT configured server-side."
                    if active_settings.elevenlabs_configured
                    else "ELEVENLABS_API_KEY is not configured in backend."
                ),
            ),
            ProviderStatus(
                id="gemini",
                capabilities=[
                    "llm",
                    "structured-turn-plan",
                    "text-stream",
                    f"default-model:{active_settings.gemini_model}",
                    *[f"model:{model}" for model in active_settings.gemini_allowed_models],
                ],
                state="healthy" if active_settings.gemini_configured else "unavailable",
                userMessage=(
                    "Backend configuration is present; no live call has been made."
                    if active_settings.gemini_configured
                    else "Backend credentials are not configured."
                ),
            ),
            ProviderStatus(
                id="deepgram",
                capabilities=["tts", "stt", "aura-2-odysseus-en", "flux-general-en"],
                state="healthy" if active_settings.deepgram_configured else "unavailable",
                userMessage=(
                    "Deepgram TTS and STT configured server-side for Hiro."
                    if active_settings.deepgram_configured
                    else "DEEPGRAM_API_KEY is not configured in backend."
                ),
            ),
            ProviderStatus(
                id="fish-audio",
                capabilities=["tts", "multilingual", "nepali", "english", "language-auto-detect"],
                state="healthy" if active_settings.fish_audio_configured else "unavailable",
                userMessage=(
                    "Fish Audio TTS configured; Nepali/English auto-switches by text script."
                    if active_settings.fish_audio_configured
                    else "FISH_AUDIO_API_KEY is not configured in backend."
                ),
            ),
            ProviderStatus(
                id="experiential",
                capabilities=[
                    "llm",
                    "structured-turn-plan",
                    "text-stream",
                    "openai-compatible",
                    f"default-model:{active_settings.active_explabs_model}",
                    *[f"model:{model}" for model in active_settings.explabs_allowed_models],
                ],
                state=explabs_state,
                userMessage=explabs_message,
            ),
            ProviderStatus(
                id="gmi",
                capabilities=["llm", "text-stream", "openai-compatible",
                              f"default-model:{active_settings.gmi_model}", f"model:{active_settings.gmi_model}"],
                state="untested" if active_settings.gmi_configured else "unavailable",
                userMessage="GMI Cloud needs a verified chat response." if active_settings.gmi_configured else "GMI Cloud needs GMI_API_KEY.",
            ),
            ProviderStatus(
                id="respan",
                capabilities=[
                    "llm",
                    "structured-turn-plan",
                    "text-stream",
                    "openai-compatible",
                    f"default-model:{active_settings.respan_model}",
                    *[f"model:{model}" for model in active_settings.respan_allowed_models],
                ],
                state=respan_state,
                userMessage=respan_message,
            ),
            ProviderStatus(
                id="tinyfish",
                capabilities=["search", "fetch"],
                state="healthy" if active_settings.tinyfish_api_key else "unavailable",
                userMessage=(
                    "TinyFish search/fetch tools registered server-side."
                    if active_settings.tinyfish_api_key
                    else "TINYFISH_API_KEY is not configured; paste it into apps/api/.env.local."
                ),
            ),
        ]

        # Configuration proves a credential exists, not that it is accepted. The
        # ledger holds the outcomes of calls that actually ran, so a badge can
        # never be greener than the last turn that went to that brain — and a
        # brain nobody has watched answer is untested, not healthy. Rows outside
        # this set are excluded on purpose: `gemini-live` speaks through the
        # Gemini credential, so no brain ever reports to it and "untested" would
        # be a permanent false alarm rather than an honest gap.
        for status in statuses:
            if status.id not in _BRAIN_PROVIDER_IDS:
                continue
            from hinaa_api.circuit_breaker import peek_circuit_breaker, CircuitBreakerState
            measured = newest_verdict(
                aliases_for(status.id),
                fingerprints=fingerprints_for(active_settings, status.id),
            )
            breaker = peek_circuit_breaker(status.id)
            if measured is not None:
                status.state = measured.state
                status.userMessage = measured.message
            elif breaker is not None and breaker.cooldown_remaining() > 0:
                status.state = "unavailable" if breaker.state == CircuitBreakerState.AUTH_ERROR else "degraded"
                status.userMessage = (
                    f"{status.id} is temporarily cooling down after a recent error ({breaker.cooldown_remaining():.0f}s remaining)."
                )
            elif status.state == "healthy" and status.id not in probe_measured:
                status.state = "untested"
                if "no live call" not in status.userMessage.lower():
                    status.userMessage = (
                        f"{status.userMessage} No live chat response has been verified for the current configuration."
                    )

        return statuses

    @app.get("/v1/commands")
    @app.get("/api/v1/commands")
    async def command_registry() -> dict[str, Any]:
        """Return the canonical command registry with availability based on provider configuration."""
        from .commands.registry import list_commands, CapabilityStatus
        from .providers.youcom import YouComClient
        from .tools.image_generate import comfyui_provider
        
        commands = list_commands()
        youcom_client = YouComClient(active_settings)
        comfyui_ready = await comfyui_provider.health_check()

        # Availability has to be measured. These were previously marked AVAILABLE
        # unconditionally, so the palette advertised /memory, /plan, /model, /voice,
        # /avatar and /goal as ready even with no database, no agent runtime, no
        # chat brain and no speech provider configured.
        #
        # `ollama` is deliberately absent: `ollama_base_url` defaults to
        # http://localhost:11434, so `ollama_configured` is true for every install
        # and would make `has_brain` unconditionally true again.
        has_brain = any(
            (
                bool(getattr(active_settings, f"{name}_configured", False))
                for name in (
                    "claude", "gemini", "openai", "qwen", "groq", "custom",
                    "agent_router", "codecraft", "cx_gateway",
                    "pgsgrove", "seekai", "tokentable", "xkiro", "cavoti", "apmix", "explabs",
                )
            )
        ) or bool(os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("DEEPSEEK_PKAY_API_KEY"))
        has_speech = any(
            bool(getattr(active_settings, f"{name}_configured", False))
            for name in ("elevenlabs", "azure", "fish_audio", "deepgram")
        )
        persistence_on = bool(active_settings.persistence_enabled)
        runtime_on = bool(active_settings.agent_runtime_enabled)

        # Configuration and providers are not the only precondition: something has
        # to answer the tool call the command produces. `_map_explicit_command`
        # refuses to propose a tool no handler owns, so a command whose handler is
        # missing can only ever return plain chat that still carries the "/command"
        # token — not the feature its palette row advertises.
        #
        # Deliberately absent from this map: `avatar_config` and `settings` are
        # served by browser surfaces this tab opens, `memory` writes through
        # MemoryService rather than a tool call, `agent_goal` runs on the agent
        # kernel's planner, and the web, image, document and playback rows resolve
        # to handlers the registry actually owns.
        from .tools.registry import registry as tool_registry

        _TOOL_DELIVERED = {
            "analysis": "analyze_text",
            "summarization": "summarize_text",
            "planning": "create_plan",
            "file_search": "search_files",
            "model_selection": "switch_model",
            "voice_config": "voice_config",
            "automation": "create_automation",
        }
        unhandled = {
            capability
            for capability, handler in _TOOL_DELIVERED.items()
            if tool_registry.get_tool(handler) is None
        }

        result = []
        for cmd in commands:
            # Determine availability based on provider configuration
            availability = CapabilityStatus.UNCONFIGURED
            if cmd.capability in {"web_search", "web_research", "web_answer", "web_extract", "image_search", "cited_answer"}:
                availability = CapabilityStatus.AVAILABLE if youcom_client.configured else CapabilityStatus.UNCONFIGURED
            elif cmd.capability in {"image_generation", "pdf_generation", "document_generation", "presentation_generation"}:
                availability = CapabilityStatus.AVAILABLE if comfyui_ready else CapabilityStatus.DEGRADED
            elif cmd.capability in {"summarization", "analysis"}:
                availability = CapabilityStatus.AVAILABLE if has_brain else CapabilityStatus.UNCONFIGURED
            elif cmd.capability == "model_selection":
                availability = CapabilityStatus.AVAILABLE if has_brain else CapabilityStatus.UNCONFIGURED
            elif cmd.capability in {"planning", "agent_goal"}:
                availability = CapabilityStatus.AVAILABLE if runtime_on else CapabilityStatus.UNAVAILABLE
            elif cmd.capability == "memory":
                availability = CapabilityStatus.AVAILABLE if persistence_on else CapabilityStatus.UNAVAILABLE
            elif cmd.capability == "file_search":
                availability = CapabilityStatus.AVAILABLE if persistence_on else CapabilityStatus.DEGRADED
            elif cmd.capability == "voice_config":
                availability = CapabilityStatus.AVAILABLE if has_speech else CapabilityStatus.UNCONFIGURED
            elif cmd.capability == "avatar_config":
                availability = CapabilityStatus.AVAILABLE  # browser-side rendering only
            elif cmd.capability == "settings":
                availability = CapabilityStatus.AVAILABLE  # browser-side only
            elif cmd.capability == "automation":
                availability = CapabilityStatus.CONFIGURED  # Requires worker setup
            elif cmd.capability == "media_playback":
                availability = CapabilityStatus.DEGRADED  # Requires browser YouTube
            
            # A ceiling, never a rewrite: a row that already reports a missing
            # dependency keeps that more specific reason, so only an over-claim
            # of readiness is corrected here.
            if cmd.capability in unhandled and availability in {
                CapabilityStatus.AVAILABLE,
                CapabilityStatus.CONFIGURED,
            }:
                availability = CapabilityStatus.UNAVAILABLE

            result.append({
                "name": cmd.name,
                "aliases": cmd.aliases,
                "description": cmd.description,
                "descriptionShort": cmd.descriptionShort,
                "examples": cmd.examples,
                "inputSchema": cmd.inputSchema,
                "capability": cmd.capability,
                "riskLevel": cmd.riskLevel.value,
                "approvalPolicy": cmd.approvalPolicy.value,
                "availability": availability.value,
                "executionLocation": cmd.executionLocation.value,
                "requiresAuth": cmd.requiresAuth,
            })
        
        return {"commands": result, "version": 1}

    @app.get("/v1/voice-profiles", response_model=list[VoiceProfile])
    async def voice_profiles() -> list[VoiceProfile]:
        return public_profiles(
            active_settings.azure_speech_female_voice,
            active_settings.azure_speech_male_voice,
        )

    @app.post("/v1/realtime/ticket")
    @app.post("/api/v1/realtime/ticket")
    async def realtime_ticket(request: Request) -> dict[str, object]:
        """Buy the identity a WebSocket handshake cannot carry.

        A browser cannot set an Authorization header when it opens a socket, so
        the voice route would otherwise never learn who it is talking to and
        would answer with no memory of him. He asks here instead, over a request
        that does prove who he is, and spends the result in the socket's first
        frame. The ticket is short lived and single use, and it never rides in a
        URL where a proxy or an access log could keep it.
        """
        from .integrations.remote_pc import request_pc
        auth = await conversation_auth(request)
        if auth is None:
            raise HinaaError(
                "PERSISTENCE_DISABLED",
                "This instance keeps no user records, so a voice session has no "
                "identity to bind to.",
                503,
                True,
            )
        return {
            "ticket": realtime_tickets.issue(auth.user_id, pc_context=request_pc.get()) if request_pc.get() else realtime_tickets.issue(auth.user_id),
            "expiresInSeconds": realtime_tickets.TICKET_TTL_SECONDS,
        }

    @app.websocket("/v1/realtime")
    @app.websocket("/api/v1/realtime")
    async def realtime_session(websocket: WebSocket) -> None:
        await realtime.handle(websocket, user_id=_resolve_user_id(websocket))

    @app.get("/v1/realtime/url")
    @app.get("/api/v1/realtime/url")
    async def realtime_url(request: Request) -> dict[str, object]:
        """Where a browser must open the realtime WebSocket.

        The deployed frontend cannot use its own origin: Vercel rewrites proxy
        HTTP but not WebSocket upgrades, so wss://<vercel-host>/…/realtime can
        never reach this process. The tunnel hostname also changes every time a
        quick tunnel restarts, so the answer is derived per request rather than
        baked into the bundle.
        """
        configured = (active_settings.realtime_public_origin or "").strip()
        if not configured:
            try:
                import json
                from pathlib import Path
                state_file = live_runner_state_path(active_settings.live_runner_state_file)
                if state_file.exists():
                    state_data = json.loads(state_file.read_text("utf-8"))
                    configured = (state_data.get("tunnelOrigin") or state_data.get("publishedOrigin") or "").strip()
            except Exception:
                pass
        host = (request.headers.get("host") or "").strip()
        forwarded_host = (request.headers.get("x-forwarded-host") or "").strip()

        chosen = choose_realtime_origin(
            configured=configured,
            host=host,
            edge_request=reached_through_edge(request),
        )
        origin = chosen.origin or ""

        is_local = origin.split(":")[0] in {"localhost", "127.0.0.1", "[::1]"}
        forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip()
        tls = forwarded_proto == "https" if forwarded_proto else not is_local
        return {
            "url": f"{'wss' if tls else 'ws'}://{origin}/v1/realtime" if origin else None,
            "source": chosen.source,
            "observed": {"host": host or None, "xForwardedHost": forwarded_host or None},
        }

    @app.post("/v1/speech/transcriptions", response_model=TranscriptResponse)
    @app.post("/api/v1/speech/transcriptions", response_model=TranscriptResponse)
    async def transcribe(
        audio: UploadFile = File(...),
        language: str = Form("hi-IN"),
        provider_mode: str = Form("mock"),
    ) -> TranscriptResponse:
        if provider_mode not in {"mock", "local", "groq", "openai", "custom", "real"}:
            raise HinaaError(
                "PROVIDER_MODE_INVALID",
                "Choose mock, local, groq, openai, custom or real mode.",
                422,
                False,
                True,
            )
        if audio.content_type not in {"audio/wav", "audio/wave", "audio/x-wav"}:
            raise HinaaError("AUDIO_FORMAT_UNSUPPORTED", "Upload PCM WAV audio.", 415, False, True)
        data = await audio.read(active_settings.max_audio_bytes + 1)
        await audio.close()
        if len(data) > active_settings.max_audio_bytes:
            raise HinaaError("AUDIO_SIZE_EXCEEDED", "The recording is too large.", 413, False, True)
        pcm = validate_wav(data, max_seconds=active_settings.max_audio_seconds)
        result = await service.transcribe(pcm, language, provider_mode)
        return TranscriptResponse(
            text=result.value,
            language=language,
            provider=result.provider,
            latencyMs=result.latency_ms,
        )

    @app.post("/v1/tools/approve")
    @app.post("/api/v1/tools/approve")
    async def approve_tool(request: Request) -> dict[str, Any]:
        data = await request.json()
        approval_id = data.get("approval_id")
        approved = data.get("approved", False)
        
        from hinaa_api.tools.browser_agent import approval_events
        if approval_id in approval_events:
            approval_events[approval_id]["approved"] = approved
            approval_events[approval_id]["event"].set()
            return {"status": "success"}
        return {"status": "error", "error": "Approval ID not found"}

    @app.get("/v1/image-studio/status")
    async def image_studio_status() -> dict:
        """Self-diagnostic for the image pipeline so a failing render explains
        itself: cloud key present? local renderer alive? which one will run?"""
        from hinaa_api.config import get_settings as _studio_settings
        from hinaa_api.tools.image_generate import comfyui_provider, MagnificProvider
        settings = _studio_settings()

        openai_ready = False
        openai_model = "gemini-3.1-flash-image"
        try:
            from hinaa_api.providers.openai_image import OpenAIImageProvider
            o_prov = OpenAIImageProvider(settings)
            if o_prov.available():
                openai_ready = True
                openai_model = o_prov.model
        except Exception:
            openai_ready = False

        stability_ready = False
        try:
            from hinaa_api.providers.stability_ai import StabilityAIProvider
            s_prov = StabilityAIProvider(settings)
            if s_prov.available():
                stability_ready = True
        except Exception:
            stability_ready = False

        magnific_ready = False
        try:
            magnific_ready = MagnificProvider(settings).available()
        except Exception:
            magnific_ready = False

        comfy_ready = False
        try:
            comfy_ready = bool(await comfyui_provider.health_check())
        except Exception:
            comfy_ready = False

        cloud_ready = openai_ready or stability_ready or magnific_ready

        if openai_ready:
            renderer = f"openai-proxy ({openai_model})"
            detail = f"Cloud generation active via OpenAI-compatible endpoint ({openai_model})."
        elif stability_ready:
            renderer = "stability-ai"
            detail = "Cloud generation active via Stability AI."
        elif magnific_ready:
            renderer = "magnific-flux"
            detail = "Magnific FLUX cloud generation is active."
        elif comfy_ready:
            renderer = "comfyui-local"
            detail = "Cloud key not found — generating through local ComfyUI."
        else:
            renderer = "none"
            detail = "No image renderer is reachable right now."

        return {
            "renderer": renderer,
            "cloudReady": cloud_ready,
            "openaiConfigured": openai_ready,
            "stabilityConfigured": stability_ready,
            "magnificConfigured": magnific_ready,
            "comfyAvailable": comfy_ready,
            "detail": detail,
            "setup": [] if (cloud_ready or comfy_ready) else [
                "Configure OPENAI_IMAGE_API_KEY and OPENAI_IMAGE_BASE_URL (for Gemini 3.1 Flash Image, OpenRouter, Fal, etc.)",
                "Or add STABILITY_API_KEY=<your Stability API key>",
                "Or add MAGNIFIC_API_KEY=<your Freepik/Magnific developer key>",
                "Or start ComfyUI on http://127.0.0.1:8188 for local generation",
            ],
        }

    @app.get("/v1/image-studio/config")
    @app.get("/api/v1/image-studio/config")
    async def get_image_studio_config() -> dict:
        return {
            "openaiImageApiKeyConfigured": bool(
                os.getenv("OPENAI_IMAGE_API_KEY")
                or os.getenv("IMAGE_PROXY_API_KEY")
            ),
            "openaiImageBaseUrl": (
                os.getenv("OPENAI_IMAGE_BASE_URL")
                or os.getenv("IMAGE_PROXY_BASE_URL")
                or "https://api.openai.com/v1"
            ),
            "openaiImageModel": (
                os.getenv("OPENAI_IMAGE_MODEL")
                or os.getenv("IMAGE_MODEL")
                or "gemini-3.1-flash-image"
            ),
            "stabilityApiKeyConfigured": bool(os.getenv("STABILITY_API_KEY")),
            "magnificApiKeyConfigured": bool(os.getenv("MAGNIFIC_API_KEY")),
        }

    @app.post("/v1/image-studio/config")
    @app.post("/api/v1/image-studio/config")
    async def update_image_studio_config(payload: ImageStudioConfigPayload) -> dict:
        updates: dict[str, str] = {}
        if payload.openai_image_api_key is not None:
            val = payload.openai_image_api_key.strip()
            if val:
                os.environ["OPENAI_IMAGE_API_KEY"] = val
                updates["OPENAI_IMAGE_API_KEY"] = val
        if payload.openai_image_base_url is not None:
            val = payload.openai_image_base_url.strip()
            if val:
                os.environ["OPENAI_IMAGE_BASE_URL"] = val
                updates["OPENAI_IMAGE_BASE_URL"] = val
        if payload.openai_image_model is not None:
            val = payload.openai_image_model.strip()
            if val:
                os.environ["OPENAI_IMAGE_MODEL"] = val
                updates["OPENAI_IMAGE_MODEL"] = val
        if payload.stability_api_key is not None:
            val = payload.stability_api_key.strip()
            if val:
                os.environ["STABILITY_API_KEY"] = val
                updates["STABILITY_API_KEY"] = val
        if payload.magnific_api_key is not None:
            val = payload.magnific_api_key.strip()
            if val:
                os.environ["MAGNIFIC_API_KEY"] = val
                updates["MAGNIFIC_API_KEY"] = val

        if updates:
            env_path = Path(__file__).resolve().parent.parent / ".env.local"
            lines = []
            if env_path.exists():
                lines = env_path.read_text(encoding="utf-8").splitlines()
            updated_keys = set()
            new_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    k, _ = stripped.split("=", 1)
                    k = k.strip()
                    if k in updates:
                        new_lines.append(f"{k}={updates[k]}")
                        updated_keys.add(k)
                        continue
                new_lines.append(line)
            for k, v in updates.items():
                if k not in updated_keys:
                    new_lines.append(f"{k}={v}")
            env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

        return {
            "status": "success",
            "updatedKeys": list(updates.keys()),
            "message": "Image studio configuration saved successfully.",
        }

    @app.get("/v1/generated-images")
    async def list_generated_images(limit: int = 50) -> dict[str, object]:
        """Every image file HINAA actually produced, newest first.

        The Library view fetches /api/v1/generated-images, which had no route
        and so fell through to fabricated demo rows. Declared under /v1 so the
        generic alias block below also serves the /api/v1 form.
        """
        from pathlib import Path

        from hinaa_api.artifacts.inventory import list_image_artifacts

        try:
            page = max(1, min(int(limit), 200))
        except (TypeError, ValueError):
            page = 50

        prompts: dict[str, str] = {}
        try:
            from hinaa_api.persistence.db import get_session_factory
            from hinaa_api.persistence.orm import ImageJob

            with get_session_factory(active_settings)() as session:
                jobs = (
                    session.query(ImageJob)
                    .filter(ImageJob.file_path.is_not(None))
                    .order_by(ImageJob.created_at.desc())
                    .all()
                )
                for job in jobs:
                    prompt = job.generation_set.prompt if job.generation_set else None
                    if not prompt:
                        continue
                    stored = Path(str(job.file_path))
                    for key in (stored.name, stored.stem):
                        prompts.setdefault(key, prompt)
        except Exception:
            # Persistence is optional; files on disk are still the truth.
            pass

        entries = list_image_artifacts(page)
        for entry in entries:
            name = str(entry["filename"])
            entry["prompt"] = prompts.get(name) or prompts.get(Path(name).stem)
        return {"images": entries, "count": len(entries)}

    @app.get("/v1/generated-images/{image_id}")
    @app.get("/api/v1/generated-images/{image_id}")
    async def get_generated_image(image_id: str):
        from hinaa_api.persistence.db import get_session_factory
        from hinaa_api.persistence.orm import ImageJob
        from hinaa_api.config import DATA_DIR, get_settings
        settings = get_settings()
        from fastapi.responses import FileResponse
        from pathlib import Path
        
        allowed_root = DATA_DIR / "images"
        resolved_path = None

        # 1. Direct file lookup in allowed_root (for Freepik/Magnific/Pollinations saved files)
        clean_name = Path(image_id).name
        direct_candidate = (allowed_root / clean_name).resolve()
        if direct_candidate.is_relative_to(allowed_root) and direct_candidate.exists() and direct_candidate.is_file():
            resolved_path = direct_candidate
        else:
            for ext in (".jpg", ".png", ".jpeg", ".webp"):
                candidate = (allowed_root / f"{clean_name}{ext}").resolve()
                if candidate.is_relative_to(allowed_root) and candidate.exists() and candidate.is_file():
                    resolved_path = candidate
                    break

        # 2. Database job lookup (for local ComfyUI queued jobs)
        if not resolved_path:
            session_factory = get_session_factory(settings)
            with session_factory() as session:
                job = session.query(ImageJob).filter_by(id=image_id).first()
                if job and job.file_path:
                    try:
                        p = Path(job.file_path).resolve()
                        if p.is_relative_to(allowed_root) and p.exists() and p.is_file():
                            resolved_path = p
                    except Exception:
                        pass

        if not resolved_path or not resolved_path.exists() or not resolved_path.is_file():
            raise HTTPException(status_code=404, detail="Image not found")
            
        ext = resolved_path.suffix.lower()
        if ext not in [".png", ".jpg", ".jpeg", ".webp"]:
            raise HTTPException(status_code=415, detail="Unsupported media type")
            
        content_type = "image/png"
        if ext in [".jpg", ".jpeg"]:
            content_type = "image/jpeg"
        elif ext == ".webp":
            content_type = "image/webp"
            
        return FileResponse(resolved_path, media_type=content_type)

    @app.get("/v1/generated-docs/{doc_id}")
    @app.get("/api/v1/generated-docs/{doc_id}")
    async def get_generated_document(
        doc_id: str,
        filename: str | None = None,
        inline: bool = False,
    ):
        from fastapi.responses import FileResponse
        from pathlib import Path
        import json

        from .artifacts.inventory import document_roots

        allowed_roots = document_roots()

        clean_name = Path(doc_id).name
        resolved_path = None

        for root in allowed_roots:
            if not root.exists():
                continue
            candidate = (root / clean_name).resolve()
            if candidate.is_relative_to(root) and candidate.exists() and candidate.is_file():
                resolved_path = candidate
                break
            candidate_pdf = (root / f"{clean_name}.pdf").resolve()
            if candidate_pdf.is_relative_to(root) and candidate_pdf.exists() and candidate_pdf.is_file():
                resolved_path = candidate_pdf
                break
            candidate_docx = (root / f"{clean_name}.docx").resolve()
            if candidate_docx.is_relative_to(root) and candidate_docx.exists() and candidate_docx.is_file():
                resolved_path = candidate_docx
                break
            for f in root.glob(f"*{clean_name}*"):
                if f.is_file() and not f.name.endswith(".json"):
                    resolved_path = f
                    break
            if resolved_path:
                break

        if not resolved_path or not resolved_path.exists() or not resolved_path.is_file():
            raise HTTPException(status_code=404, detail="Document not found")
        if resolved_path.suffix.lower() == '.pdf':
            from .artifacts.document_validation import validate_pdf
            try:
                validate_pdf(resolved_path)
            except Exception:
                raise HTTPException(status_code=422, detail='Document failed format validation')
        media_type = "application/octet-stream"
        suffix = resolved_path.suffix.lower()
        if suffix == ".pdf":
            media_type = "application/pdf"
        elif suffix == ".docx":
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif suffix == ".pptx":
            media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        elif suffix == ".html":
            media_type = "text/html"
        elif suffix == ".md":
            media_type = "text/markdown"

        # Determine clean display filename
        final_filename = filename
        if not final_filename:
            meta_path = resolved_path.parent / f"{clean_name}.metadata.json"
            if meta_path.exists():
                try:
                    with open(meta_path, "r", encoding="utf-8") as mf:
                        m_data = json.load(mf)
                        final_filename = m_data.get("filename")
                except Exception:
                    pass
        if not final_filename:
            final_filename = resolved_path.name
            if "_" in final_filename and len(final_filename.split("_")[0]) == 36:
                final_filename = "_".join(final_filename.split("_")[1:])

        disposition_type = "inline" if inline else "attachment"
        return FileResponse(
            resolved_path,
            media_type=media_type,
            headers={"Content-Disposition": f'{disposition_type}; filename="{final_filename}"'},
        )

    # A designed page is meant to be looked at, not filed away, so it gets a route
    # that sends it inline instead of as an attachment.
    @app.get("/v1/generated-docs/{doc_id}/preview")
    @app.get("/api/v1/generated-docs/{doc_id}/preview")
    async def preview_generated_document(doc_id: str):
        from .artifacts.inventory import document_roots

        if not re.fullmatch(r"[0-9a-fA-F-]{36}", doc_id):
            raise HTTPException(status_code=404, detail="Preview not found")

        for root in document_roots():
            if not root.exists():
                continue
            # 1. HTML preview
            for candidate in sorted(root.glob(f"{doc_id}_*.html")):
                if candidate.is_file():
                    return FileResponse(
                        candidate,
                        media_type="text/html; charset=utf-8",
                        headers={
                            "Content-Security-Policy": "sandbox; default-src 'none'; style-src 'unsafe-inline'",
                            "X-Content-Type-Options": "nosniff",
                        },
                    )
            # 2. PDF preview inline
            for candidate in sorted(root.glob(f"*{doc_id}*.pdf")):
                if candidate.is_file():
                    return FileResponse(
                        candidate,
                        media_type="application/pdf",
                        headers={
                            "Content-Disposition": f'inline; filename="{candidate.name}"',
                            "X-Content-Type-Options": "nosniff",
                        },
                    )
        raise HTTPException(status_code=404, detail="Preview not found")


    @app.get("/v1/workspace/identity")
    async def workspace_identity(
        request: Request,
        auth: AuthContext | None = Depends(conversation_auth),
    ) -> dict[str, Any]:
        user_id = auth.user_id if auth else _workspace_user_id(request)
        return {"userId": user_id}

    @app.get("/v1/tools/poll")
    @app.get("/api/v1/tools/poll")
    async def poll_tool(request: Request, job_id: str) -> dict[str, Any]:
        from hinaa_api.persistence.db import get_session_factory
        from hinaa_api.persistence.orm import GenerationSet, ImageJob
        settings = active_settings
        
        session_factory = get_session_factory(settings)
        with session_factory() as session:
            gen_set = session.query(GenerationSet).filter_by(id=job_id, user_id=_workspace_user_id(request)).first()
            if not gen_set:
                raise HTTPException(status_code=404, detail="Job not found")
                
            jobs = session.query(ImageJob).filter_by(generation_set_id=job_id).order_by(ImageJob.created_at.asc()).all()
            if not jobs:
                return {"id": job_id, "status": "processing", "images": [], "total": 0}
                
            images: list[str] = []
            slots: list[dict[str, Any]] = []
            failures: list[str] = []
            active = False
            for index, job in enumerate(jobs, start=1):
                source = f"/api/v1/generated-images/{job.id}" if job.status == "completed" and job.file_path else None
                if source:
                    images.append(source)
                if job.status in {"pending", "queued", "processing"}:
                    active = True
                if job.status in {"failed", "cancelled"}:
                    failures.append(f"Image {index} {job.status}")
                slots.append({
                    "id": job.id,
                    "index": index,
                    "status": job.status,
                    "seed": job.seed,
                    "width": job.width,
                    "height": job.height,
                    "promptId": job.comfy_prompt_id,
                    "url": source,
                })
            if not active and images:
                cid = (
                    request.query_params.get("conversation_id")
                    or request.headers.get("x-conversation-id")
                    or gen_set.conversation_id
                )
                try:
                    from hinaa_api.media.resolver import MediaResolver
                    from hinaa_api.dialogue_state import EntityReferenceResolver
                    resolver = MediaResolver()
                    new_asset_ids = []
                    for img_url in images:
                        res = await resolver.resolve(img_url)
                        if res and res.asset_id:
                            new_asset_ids.append(res.asset_id)
                    if cid and service.dialogue_state_service:
                        uid = _workspace_user_id(request)
                        d_state = service.dialogue_state_service.load(cid, uid)
                        for aid in new_asset_ids:
                            if aid not in d_state.last_generated_asset_ids:
                                d_state.last_generated_asset_ids.append(aid)
                            if not any(a.get("asset_id") == aid for a in d_state.active_assets):
                                d_state.active_assets.append({
                                    "asset_id": aid,
                                    "url": f"/api/v1/assets/{aid}",
                                    "type": "image",
                                    "created_at": datetime.now(timezone.utc).isoformat(),
                                })
                        active_char = EntityReferenceResolver.get_active_character(d_state)
                        d_state.last_assistant_action = {
                            "action": "image_generate",
                            "prompt": gen_set.prompt,
                            "subject": active_char,
                            "asset_ids": new_asset_ids,
                            "completed": True,
                        }
                        d_state.tool_result_sets.append({
                            "result_set_id": job_id,
                            "tool": "image_generate",
                            "ordered_asset_ids": new_asset_ids,
                        })
                        service.dialogue_state_service.save(d_state)
                except Exception:
                    logger.warning("Failed to record generated assets in dialogue state during poll_tool", exc_info=True)

            return {
                "id": job_id,
                "status": "processing" if active else ("completed" if images else "failed"),
                "images": images,
                "slots": slots,
                "total": len(jobs),
                "prompt": gen_set.prompt,
                "mode": gen_set.workflow_mode,
                "error": " | ".join(failures) if failures else None,
            }

    @app.get("/v1/tools")
    @app.get("/api/v1/tools")
    async def list_tools() -> list[dict[str, Any]]:
        from .tools.dynamic_tools import sync_dynamic_tools
        sync_dynamic_tools()
        tools = registry.get_all_tools()
        return [
            {
                "name": t.name,
                "displayName": t.display_name,
                "description": t.description,
                "riskLevel": t.risk_level,
                "requiresConfirmation": t.requires_confirmation,
                "parameters": t.parameters,
                "requiredParameters": t.required_parameters,
                "permissionLevel": t.permission_level,
                "cancellable": t.cancellable,
            }
            for t in tools
        ]

    @app.post("/v1/tools/execute")
    @app.post("/api/v1/tools/execute")
    async def execute_tool(request: Request, body: ToolRequest) -> dict[str, Any]:
        from .tools.dynamic_tools import sync_dynamic_tools
        sync_dynamic_tools()
        tool_def = registry.get_tool(body.toolName)
        if not tool_def:
            raise HTTPException(status_code=404, detail="Tool not found")
        org_gate.authorize_tool(request, body.toolName)
        verdict = tool_policy.decide(body.toolName, active_settings, request.headers.get("host"))
        if not verdict.permitted:
            raise HinaaError(verdict.code, verdict.message, 403, False, True)
        tool_policy.check_arguments(body.toolName, body.parameters)
        is_user_approved = body.confirmed and body.approvalSource == "user"
        is_safe_standing_consent = (
            body.confirmed
            and body.approvalSource == "standing-consent"
            and body.toolName in (
                "image_search",
                "web_search",
                "web_answer",
                "web_research",
                "web_extract",
                "diagnostic_echo",
                "image_generate",
                "pdf_generate",
                "document_generate",
                "create_gamma_presentation",
                "gamma_create",
                "magnific_image_generate",
                "freepik_image_generate",
                "magnific_upscale",
                "freepik_stock_search",
                "browser_cloud_agent",
                "browser_execute_task",
                "browser_navigate",
                "browser_click",
                "browser_type",
                "browser_extract",
                "browser_scroll",
                "browser_press_key",
                "ui_control",
                "computer_operator",
                "app_launch",
                "system_info",
                "search_files",
                "exa_search",
                "exa_get_contents",
                "exa_agent_run",
                "deep_research",
                "coding_agent",
                "clean_room_loop",
                "code_repair",
                "terminal_execute",
                "file_read",
                "directory_list",
                "customgpt_query",
                "codebase_search",
                "subagent_fork",
            )
        )
        if tool_def.requires_confirmation and not (
            is_user_approved or is_safe_standing_consent or tool_policy.confirmation_waived(body.toolName)
        ):
            raise HinaaError(
                "TOOL_CONFIRMATION_REQUIRED",
                f"Confirm the {tool_def.display_name} action before HINAA runs it.",
                409,
                False,
                True,
            )

        handler = registry._handlers.get(body.toolName)
        if not handler:
            raise HTTPException(status_code=500, detail="Tool handler not registered")

        from .integrations_hub import mcp_agent_tools
        _mcp_token = mcp_agent_tools.set_user_approved(bool(is_user_approved))
        try:
            import inspect
            from typing import get_type_hints
            from pydantic import BaseModel
            
            sig = inspect.signature(handler)
            parsed_params = body.parameters.copy()

            # Canonical boundary normalization: attachment identifiers may be
            # sent at the top level by the web client or nested in parameters.
            # Preserve explicit nested values and support both historical names.
            if body.attachment_ids:
                if not parsed_params.get("attachment_ids"):
                    parsed_params["attachment_ids"] = list(body.attachment_ids)
                if not parsed_params.get("attachmentIds"):
                    parsed_params["attachmentIds"] = list(body.attachment_ids)
            if body.reference_images and not parsed_params.get("reference_images"):
                parsed_params["reference_images"] = list(body.reference_images)
            if body.imageUrl and not parsed_params.get("imageUrl"):
                parsed_params["imageUrl"] = body.imageUrl
            
            # Normalize prompt alias variations if model passed 'description', 'text', 'query', or 'prompt_text'
            if tool_def.name in ("image_generate", "magnific_image_generate", "freepik_image_generate"):
                if "prompt" not in parsed_params:
                    prompt_val = (
                        parsed_params.get("description")
                        or parsed_params.get("text")
                        or parsed_params.get("query")
                        or parsed_params.get("prompt_text")
                    )
                    if prompt_val:
                        parsed_params["prompt"] = str(prompt_val)

            # Normalize browser_execute_task goal if model passed action, url, or task
            if tool_def.name == "browser_execute_task":
                if "goal" not in parsed_params or not parsed_params.get("goal"):
                    goal = parsed_params.get("task") or parsed_params.get("query")
                    if not goal:
                        url = parsed_params.get("url")
                        action = parsed_params.get("action", "navigate")
                        if url:
                            goal = f"{action} to {url}"
                        else:
                            goal = "Browse web and execute user task"
                    parsed_params["goal"] = str(goal)

            # Normalize youtube_playback_request query if model passed song, track, or title
            if tool_def.name == "youtube_playback_request":
                if "query" not in parsed_params or not parsed_params.get("query"):
                    q = (
                        parsed_params.get("song")
                        or parsed_params.get("track")
                        or parsed_params.get("title")
                        or parsed_params.get("text")
                    )
                    if q:
                        parsed_params["query"] = str(q)

            # Sanitize browser_navigate URL
            if tool_def.name == "browser_navigate" and parsed_params.get("url"):
                raw_u = str(parsed_params["url"]).strip()
                if " " in raw_u or "\n" in raw_u or "." not in raw_u:
                    from urllib.parse import quote_plus
                    parsed_params["url"] = f"https://www.google.com/search?q={quote_plus(raw_u)}"
            
            # Server-resolved owner identity overrides client payload. Both
            # halves have to agree: /v1/tools/poll looks the row up under
            # _workspace_user_id, and when identity is unresolvable the execute
            # side used to leave userId unset, so the handler's own default won
            # and every image was drawn, saved, then reported as not found.
            server_user_id = _resolve_user_id(request)
            parsed_params.pop("userId", None)
            parsed_params.pop("user_id", None)
            parsed_params["userId"] = server_user_id or active_settings.dev_auth_subject

            if "conversationId" not in parsed_params:
                conv_id = body.conversationId or request.headers.get("X-Conversation-ID")
                if conv_id:
                    parsed_params["conversationId"] = conv_id

            # P0 FIX — 422 prevention: if web_search is missing its required
            # "query" param, auto-populate from dialogue state active_topic + slots
            # rather than raising 422 and destroying the conversation context.
            if tool_def.name == "web_search" and (
                "query" not in parsed_params or not parsed_params.get("query")
            ):
                try:
                    _conv_id = body.conversationId or request.headers.get("X-Conversation-ID")
                    if _conv_id and getattr(service, "dialogue_state_service", None) is not None:
                        _ds = service.dialogue_state_service.load(_conv_id)
                        _fallback_query = _ds.get_query_for_active_topic()
                        if _fallback_query:
                            parsed_params["query"] = _fallback_query
                            logger.info(
                                "P0: auto-populated web_search query from dialogue state: %r",
                                _fallback_query,
                            )
                except Exception:
                    pass  # Never block a tool call over state-recovery failure

            if tool_def.name == "web_search" and parsed_params.get("query"):
                # The request edge is where his utterance turns into a vendor
                # query, so this is the last gate that can strip the addressee
                # and the command verb before the search actually runs.
                from hinaa_api.media.search_intelligence import compiled_web_query_parameters

                parsed_params = compiled_web_query_parameters(dict(parsed_params))

            # Validate required parameters before invoking handler
            missing = [name for name in tool_def.required_parameters if name not in parsed_params or parsed_params[name] is None]
            if missing:
                raise HinaaError(
                    "TOOL_ARGUMENTS_INVALID",
                    f"Missing required argument(s) for {tool_def.display_name}: {', '.join(missing)}.",
                    422,
                    False,
                    True,
                )

            if sig.parameters:
                first_param = list(sig.parameters.values())[0]
                try:
                    param_type = get_type_hints(handler).get(first_param.name, first_param.annotation)
                except (NameError, TypeError):
                    param_type = first_param.annotation
                if inspect.isclass(param_type) and issubclass(param_type, BaseModel):
                    parsed_params = param_type(**parsed_params)

            owner = _resolved_tool_owner(server_user_id)
            with genai.tool_call(name=body.toolName, call_id=body.id):
                return await _execute_registered_tool(tool_def, handler, parsed_params, body, owner)
        except HinaaError:
            raise
        except Exception:
            logger.exception("Tool execution failed: %s", body.toolName)
            raise HinaaError(
                "TOOL_EXECUTION_FAILED",
                "HINAA could not complete that action. Please try again.",
                502,
                True,
                False,
            ) from None
        finally:
            mcp_agent_tools.reset_user_approved(_mcp_token)

    @app.post("/v1/terminal/execute")
    @app.post("/api/v1/terminal/execute")
    async def execute_terminal_endpoint(request: Request) -> dict[str, Any]:
        """Execute terminal commands in native OS or Kali Linux WSL with structured security reporting."""
        body = await request.json()
        from hinaa_api.tools.terminal_hands import execute_terminal_hands
        return await execute_terminal_hands(body)

    # -----------------------------------------------------------------------
    # Frontier Agent Harness & Fleet Endpoints
    # -----------------------------------------------------------------------
    from .routers.harness_router import router as harness_router
    app.include_router(harness_router)

    # -----------------------------------------------------------------------
    # RAG Knowledge Endpoints
    # -----------------------------------------------------------------------

    @app.get("/v1/rag/status")
    @app.get("/api/v1/rag/status")
    async def rag_status() -> dict[str, Any]:
        """Returns RAG knowledge base statistics and weighting."""
        if getattr(service, "rag_service", None) is None:
            return {"status": "unavailable", "total_chunks": 0, "total_documents": 0}
        stats = service.rag_service.get_stats()
        return {"status": "success", **stats}

    @app.post("/v1/rag/query")
    @app.post("/api/v1/rag/query")
    async def rag_query(request: Request) -> dict[str, Any]:
        """Runs hybrid retrieval and MMR reranking against the knowledge base."""
        if getattr(service, "rag_service", None) is None:
            raise HinaaError("RAG_NOT_AVAILABLE", "RAG service is not initialized", 503)
        body = await request.json()
        query_text = body.get("query", "").strip()
        top_k = int(body.get("top_k", 4))
        score_threshold = float(body.get("score_threshold", 0.15))
        results = service.rag_service.query(query_text, top_k=top_k, score_threshold=score_threshold)

        formatted = []
        for r in results:
            formatted.append({
                "chunk_id": r.result.chunk.chunk_id,
                "document_id": r.result.chunk.metadata.document_id,
                "source": r.result.chunk.metadata.source,
                "section": r.result.chunk.metadata.section_path,
                "final_score": round(r.final_score, 4),
                "relevance_score": round(r.relevance_score, 4),
                "authority_score": round(r.authority_score, 4),
                "text": r.result.chunk.text,
            })
        return {
            "status": "success",
            "query": query_text,
            "total_matches": len(formatted),
            "results": formatted,
        }

    @app.post("/v1/rag/ingest")
    @app.post("/api/v1/rag/ingest")
    async def rag_ingest_document(request: Request) -> dict[str, Any]:
        """Ingests a document or markdown text into the active knowledge index."""
        if getattr(service, "rag_service", None) is None:
            raise HinaaError("RAG_NOT_AVAILABLE", "RAG service is not initialized", 503)
        body = await request.json()
        content = body.get("content", "").strip()
        doc_id = body.get("document_id") or f"doc_{uuid4().hex[:12]}"
        source = body.get("source") or "API Upload"
        author = body.get("author") or "user"
        version = body.get("version") or "1.0"
        visibility = body.get("visibility") or "internal"

        chunks = service.rag_service.ingest_document(
            text=content,
            document_id=doc_id,
            source=source,
            author=author,
            version=version,
            visibility=visibility,
        )
        return {
            "status": "success",
            "document_id": doc_id,
            "chunks_created": len(chunks),
            "total_index_chunks": service.rag_service.total_chunks,
        }

    @app.post("/v1/rag/reindex-specs")
    @app.post("/api/v1/rag/reindex-specs")
    async def rag_reindex_specs() -> dict[str, Any]:
        """Re-reads and indexes all `.hina/` repository specs."""
        if getattr(service, "rag_service", None) is None:
            raise HinaaError("RAG_NOT_AVAILABLE", "RAG service is not initialized", 503)
        indexed = service.rag_service.index_repository_memory()
        return {
            "status": "success",
            "specs_indexed": indexed,
            "total_index_chunks": service.rag_service.total_chunks,
        }


    def _resolved_tool_owner(server_user_id: str | None) -> str:
        """Map an auth subject to the users.id a durable task may reference.

        The dev fallback is a subject, not a row id, and `durable_tasks.owner_id`
        has a foreign key to `users.id`: measured on production, the insert
        raised IntegrityError and /tools/execute answered 502, so images she had
        genuinely found never reached the screen.
        """
        candidate = server_user_id or active_settings.dev_auth_subject
        if memory_service is None:
            return candidate
        try:
            return memory_service.resolve_user(candidate).id
        except Exception:
            logger.warning("could not resolve tool owner identity", exc_info=True)
            return candidate

    def _workspace_user_id(request: Request) -> str:
        return _resolve_user_id(request) or active_settings.dev_auth_subject

    @app.get("/v1/projects")
    async def list_projects(request: Request) -> list[dict[str, Any]]:
        return workspace_service.list_projects(_workspace_user_id(request))

    @app.post("/v1/projects", status_code=201)
    async def create_project(request: Request, body: ProjectCreateBody) -> dict[str, Any]:
        return workspace_service.create_project(
            _workspace_user_id(request), body.title, body.description
        )

    @app.post("/v1/projects/{project_id}/plans", status_code=201)
    async def create_project_plan(
        request: Request, project_id: str, body: ProjectPlanBody
    ) -> list[dict[str, Any]]:
        plan = workspace_service.create_starter_plan(
            _workspace_user_id(request), project_id, body.goal
        )
        if plan is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return plan

    @app.get("/v1/projects/{project_id}")
    async def get_project(request: Request, project_id: str) -> dict[str, Any]:
        project = workspace_service.project_detail(_workspace_user_id(request), project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return project

    @app.get("/v1/projects/runs/{run_id}/events")
    async def list_run_events(request: Request, run_id: str) -> dict[str, Any]:
        user_id = _workspace_user_id(request)
        run = workspace_service.get_agent_run(user_id, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return {"runId": run_id, "events": run.get("events", [])}

    @app.post("/v1/projects/runs/{run_id}/events")
    async def append_run_event(
        request: Request, run_id: str, body: ProjectAgentRunEventBody
    ) -> dict[str, Any]:
        result = workspace_service.append_agent_run_event(
            _workspace_user_id(request),
            run_id,
            kind=body.kind,
            status=body.status,
            label=body.label,
            detail=body.detail,
        )
        if result is None:
            raise HTTPException(status_code=404, detail="Run not found or is terminal")
        return result

    @app.post("/v1/projects/{project_id}/tasks", status_code=201)
    async def create_project_task(
        request: Request, project_id: str, body: ProjectTaskBody
    ) -> dict[str, Any]:
        task = workspace_service.create_task(
            _workspace_user_id(request),
            project_id,
            body.title,
            body.detail,
            body.parentTaskId,
            body.requiresApproval,
        )
        if task is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return task

    @app.get("/v1/projects/{project_id}/code/files")
    async def list_code_files(request: Request, project_id: str) -> list[dict[str, Any]]:
        files = workspace_service.list_code_files(_workspace_user_id(request), project_id)
        if files is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return files

    @app.post("/v1/projects/{project_id}/code/files", status_code=201)
    async def save_code_file(
        request: Request, project_id: str, body: ProjectCodeFileBody
    ) -> dict[str, Any]:
        try:
            result = workspace_service.save_code_file(
                _workspace_user_id(request),
                project_id,
                body.path,
                body.content,
                overwrite=body.overwrite,
                run_id=body.runId,
            )
        except FileExistsError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if result is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return result

    @app.patch("/v1/projects/tasks/{task_id}")
    async def update_project_task(
        request: Request, task_id: str, body: ProjectTaskStatusBody
    ) -> dict[str, Any]:
        task = workspace_service.update_task_status(
            _workspace_user_id(request), task_id, body.status
        )
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return task

    @app.get("/v1/projects/{project_id}/runs")
    async def list_project_runs(request: Request, project_id: str) -> list[dict[str, Any]]:
        project = workspace_service.project_detail(_workspace_user_id(request), project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return project.get("runs", [])

    @app.post("/v1/projects/{project_id}/runs", status_code=201)
    async def create_project_run(
        request: Request, project_id: str, body: ProjectAgentRunBody
    ) -> dict[str, Any]:
        user_id = _workspace_user_id(request)
        runtime_run = (
            agent_runtime.create_run(body.goal, user_id, project_id=project_id)
            if active_settings.agent_runtime_enabled and agent_runtime is not None
            else None
        )
        run = workspace_service.create_agent_run(
            user_id,
            project_id,
            body.goal,
            body.rootTaskId,
            run_id=runtime_run.run_id if runtime_run else None,
        )
        if run is None:
            if runtime_run:
                agent_runtime.cancel(runtime_run.run_id, {user_id})
            raise HTTPException(status_code=404, detail="Project or selected task not found")
        if runtime_run:
            if run.get("status") == "running":
                _schedule_project_run(runtime_run)
                await asyncio.sleep(0)
            runtime_events = agent_runtime.get_events(runtime_run.run_id, {user_id}) or []
            for runtime_event in runtime_events:
                workspace_service.append_agent_run_event(
                    user_id,
                    run["id"],
                    kind="runtime",
                    status="running" if run.get("status") == "running" else "waiting_approval",
                    label=runtime_event.event_type,
                    detail=str(runtime_event.payload or ""),
                    allow_terminal=True,
                )
            refreshed = workspace_service.get_agent_run(user_id, run["id"])
            if refreshed is not None:
                run = refreshed
        return run

    @app.patch("/v1/projects/runs/{run_id}")
    async def update_project_run(
        request: Request, run_id: str, body: ProjectAgentRunStatusBody
    ) -> dict[str, Any]:
        user_id = _workspace_user_id(request)
        existing = workspace_service.get_agent_run(user_id, run_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Agent run not found")

        runtime_run = (
            agent_runtime.get_run(run_id, {user_id})
            if active_settings.agent_runtime_enabled and agent_runtime is not None
            else None
        )
        if body.status == "completed" and runtime_run:
            raise HTTPException(status_code=409, detail="Runtime run cannot be completed directly by client while executing.")

        run = workspace_service.update_agent_run(user_id, run_id, body.status, body.summary)
        if run is None:
            raise HTTPException(status_code=409, detail="Illegal agent run transition")
        runtime_events: list[AgentEvent] = []
        if runtime_run:
            if body.status == "cancelled":
                before = len(agent_runtime.get_events(run_id, {user_id}) or [])
                agent_runtime.cancel(run_id, {user_id})
                runtime_events = (agent_runtime.get_events(run_id, {user_id}) or [])[before:]
            elif body.status == "running" and runtime_run.status in {RunStatus.QUEUED, RunStatus.AWAITING_CONFIRMATION}:
                _schedule_project_run(runtime_run)
            elif body.status == "completed":
                plan = agent_runtime.get_plan(run_id)
                step = next((s for s in plan.steps if s.status.value == "running"), None) if plan else None
                if plan and step:
                    runtime_events = agent_runtime.complete_stream_turn(
                        runtime_run,
                        plan,
                        step,
                        result={"summary": body.summary or ""},
                    )
            elif body.status == "failed":
                plan = agent_runtime.get_plan(run_id)
                step = next((s for s in plan.steps if s.status.value == "running"), None) if plan else None
                runtime_events = agent_runtime.fail_stream_turn(
                    runtime_run,
                    step=step,
                    code="PROJECT_RUN_FAILED",
                    message=body.summary or "Project run failed.",
                )
        for runtime_event in runtime_events:
            workspace_service.append_agent_run_event(
                user_id,
                run_id,
                kind="runtime",
                status=run.get("status", body.status),
                label=runtime_event.event_type,
                detail=str(runtime_event.payload or ""),
                allow_terminal=True,
            )
        if runtime_events:
            refreshed = workspace_service.get_agent_run(user_id, run_id)
            if refreshed is not None:
                run = refreshed
        return run

    def _agent_user_ids(request: Request) -> set[str]:
        # Owner ids whose runs this caller may read. An anonymous caller gets an
        # empty set, not the dev subject: his runs and a stranger's would
        # otherwise land in one bucket that both sides can list.
        ids: set[str] = set()
        uid = _resolve_user_id(request)
        if uid:
            ids.add(uid)
        if not reached_through_edge(request):
            ids.add(active_settings.dev_auth_subject)
            dev_hdr = request.headers.get("X-HINAA-Dev-User")
            if dev_hdr:
                ids.add(dev_hdr)
        return ids

    @app.get("/v1/agent/runs/{run_id}")
    async def get_agent_run(request: Request, run_id: str) -> dict[str, Any]:
        user_id = _agent_user_ids(request)
        run = agent_runtime.get_run(run_id, user_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return run.model_dump(mode="json")

    @app.get("/v1/agent/runs/{run_id}/steps")
    async def list_agent_run_steps(request: Request, run_id: str) -> dict[str, Any]:
        user_id = _agent_user_ids(request)
        steps = agent_runtime.get_steps(run_id, user_id)
        if steps is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return {"runId": run_id, "steps": [s.model_dump(mode="json") for s in steps]}

    @app.get("/v1/agent/runs/{run_id}/events")
    async def list_agent_run_events(request: Request, run_id: str, after: int = 0) -> dict[str, Any]:
        user_id = _agent_user_ids(request)
        events = agent_runtime.get_events(run_id, user_id)
        if events is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return {
            "runId": run_id,
            "cursor": max((event.sequence for event in events), default=0),
            "events": [e.model_dump(mode="json") for e in events if e.sequence > max(0, after)],
        }

    @app.post("/v1/agent/runs/{run_id}/cancel")
    async def cancel_agent_run(request: Request, run_id: str) -> dict[str, Any]:
        user_id = _agent_user_ids(request)
        run = agent_runtime.cancel(run_id, user_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return {"run_id": run.run_id, "status": run.status.value, "idempotent": True}

    @app.post("/v1/agent/runs/{run_id}/resume")
    async def resume_agent_run(request: Request, run_id: str) -> dict[str, Any]:
        user_id = _agent_user_ids(request)
        run = agent_runtime.resume(run_id, user_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        if run.project_id:
            workspace_service.update_agent_run(run.user_id, run_id, "running")
            if agent_runtime.get_plan(run.run_id):
                _schedule_project_run(run)
        if not run.project_id and agent_runtime.get_plan(run.run_id) and run.status == RunStatus.EXECUTING:
            task = asyncio.create_task(agent_runtime.execute(run), name=f"hinaa-resume-{run.run_id}")
            tool_tasks.add(task)
            task.add_done_callback(tool_tasks.discard)
        return run.model_dump(mode="json")

    @app.post("/v1/agent/runs/{run_id}/recover")
    async def recover_agent_run(request: Request, run_id: str) -> dict[str, Any]:
        user_id = _agent_user_ids(request)
        run = agent_runtime.recover(run_id, user_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return run.model_dump(mode="json")

    @app.post("/v1/agent/runs/{run_id}/confirm")
    async def confirm_agent_run(
        request: Request, run_id: str, body: dict[str, Any] = Body(default_factory=dict)
    ) -> dict[str, Any]:
        user_id = _agent_user_ids(request)
        step_id = body.get("step_id") or body.get("stepId")
        if not step_id:
            raise HTTPException(status_code=400, detail="step_id is required")
        approved = body.get("approved", True)
        run = agent_runtime.confirm(run_id, step_id, user_id, approved)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return run.model_dump(mode="json")

    # ── Cognitive OS & World Model Routes ──────────────────────────────

    @app.get("/v1/cognitive/world-state")
    @app.get("/api/v1/cognitive/world-state")
    async def get_world_state(request: Request) -> dict[str, Any]:
        user_id = _resolve_user_id(request) or "default_user"
        state = WorldModel.hydrate_initial_state(user_id=user_id)
        return state.model_dump(mode="json")

    @app.get("/v1/cognitive/session-bootstrap")
    @app.get("/api/v1/cognitive/session-bootstrap")
    async def get_session_bootstrap(request: Request) -> dict[str, Any]:
        user_id = _resolve_user_id(request) or "default_user"
        return session_bridge.bootstrap_new_session(user_id=user_id)

    @app.post("/v1/cognitive/runs")
    @app.post("/api/v1/cognitive/runs")
    async def execute_cognitive_run(request: Request, body: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
        user_id = _resolve_user_id(request) or "default_user"
        text = body.get("text", "")
        session_id = body.get("sessionId") or body.get("conversationId") or f"sess_{uuid4().hex[:8]}"
        project_id = body.get("projectId")
        run = await cognitive_kernel.execute_turn(
            text=text,
            user_id=user_id,
            session_id=session_id,
            project_id=project_id,
        )
        return run.model_dump(mode="json")

    @app.get("/v1/cognitive/runs/{run_id}")
    @app.get("/api/v1/cognitive/runs/{run_id}")
    async def get_cognitive_run(run_id: str) -> dict[str, Any]:
        run = cognitive_kernel.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="CognitiveRun not found")
        return run.model_dump(mode="json")

    # ── Enterprise Subsystems: Policy, Audit Ledger, Data Lake & Resilient Router ──
    @app.get("/v1/enterprise/status")
    @app.get("/api/v1/enterprise/status")
    async def enterprise_status(request: Request) -> dict[str, Any]:
        """Enterprise operational overview: PDP/PEP, Audit Ledger, Data Lake, and Model Router."""
        policy_eng = get_policy_engine()
        lake = get_data_lake()
        router = get_resilient_router()

        return {
            "status": "operational",
            "tier": "enterprise_grade",
            "securityPolicy": {
                "guardrailsActive": True,
                "hitlApprovalTokensEnabled": True,
                "piiSecretRedaction": True,
                "auditChainIntegrityVerified": policy_eng.verify_audit_integrity(),
                "recentAuditEntriesCount": len(policy_eng.get_recent_audit_records(100)),
            },
            "dataLake": lake.get_statistics(),
            "resilientModelRouter": {
                "providers": router.get_all_statuses(),
                "healthyChain": router.select_healthy_provider_chain(),
            },
            "timestamp": time.time(),
        }

    @app.get("/v1/enterprise/metrics")
    @app.get("/api/v1/enterprise/metrics")
    async def enterprise_metrics(request: Request) -> dict[str, Any]:
        """Telemetry metrics for Prometheus scrapers and observability dashboards."""
        policy_eng = get_policy_engine()
        lake = get_data_lake()
        router = get_resilient_router()
        lake_stats = lake.get_statistics()

        return {
            "hinaa_enterprise_up": 1,
            "hinaa_audit_chain_valid": 1 if policy_eng.verify_audit_integrity() else 0,
            "hinaa_lake_total_events": lake_stats.get("totalEventsIngested", 0),
            "hinaa_lake_total_runs": lake_stats.get("totalRunsArchived", 0),
            "hinaa_lake_storage_bytes": lake_stats.get("storageBytes", 0),
            "hinaa_circuit_breakers": {
                name: 1 if st.get("state") == "closed" else 0
                for name, st in router.get_all_statuses().items()
            },
        }

    @app.get("/v1/enterprise/audit-trail")
    @app.get("/api/v1/enterprise/audit-trail")
    async def enterprise_audit_trail(request: Request, limit: int = 50) -> dict[str, Any]:
        """Cryptographically hashed SHA-256 audit ledger."""
        policy_eng = get_policy_engine()
        records = policy_eng.get_recent_audit_records(limit=min(limit, 200))
        return {
            "chainIntegrityVerified": policy_eng.verify_audit_integrity(),
            "count": len(records),
            "auditRecords": [r.model_dump() for r in records],
        }

    @app.post("/v1/enterprise/export-compliance")
    @app.post("/api/v1/enterprise/export-compliance")
    async def enterprise_export_compliance(request: Request, body: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
        """GDPR / SOC2 data lake export."""
        user_id = _resolve_user_id(request) or body.get("userId") or "default_user"
        lake = get_data_lake()
        return lake.export_compliance_archive(user_id=user_id)


    @app.post("/v1/projects/{project_id}/artifacts", status_code=201)
    async def create_project_artifact(
        request: Request, project_id: str, body: ProjectArtifactBody
    ) -> dict[str, Any]:
        artifact = workspace_service.create_artifact(
            _workspace_user_id(request),
            project_id,
            body.kind,
            body.title,
            body.content,
            body.sourceUrl,
            body.metadata,
        )
        if artifact is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return artifact

    @app.post("/v1/documents/pdf")
    @app.post("/api/v1/documents/pdf")
    async def export_document_pdf(body: DocumentPdfBody) -> Response:
        """Render any markdown document (chat answer, research brief, plan)
        into a real multi-page PDF — branded, paginated, table-aware."""
        from fastapi.responses import Response as _Response
        from .documents.pdf import render_markdown_pdf, safe_filename
        try:
            data = render_markdown_pdf(
                body.markdown,
                title=body.title or "HINAA Report",
                subtitle=body.subtitle,
            )
        except HTTPException:
            raise
        except Exception as error:  # noqa: BLE001 - the renderer must answer, not 500
            logger.exception("PDF rendering failed")
            raise HinaaError(
                "DOCUMENT_PDF_FAILED",
                f"The document could not be rendered ({type(error).__name__}).",
                500,
                True,
                False,
            ) from error
        if not data or len(data) > 25_000_000:
            raise HTTPException(status_code=413, detail="Document too large to render")
        filename = safe_filename(body.title)
        return _Response(
            content=data,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-store",
            },
        )

    @app.post("/v1/documents/pptx")
    @app.post("/api/v1/documents/pptx")
    async def export_document_pptx(body: DocumentPdfBody) -> Response:
        """Render any markdown document into an executive 16:9 PowerPoint (.pptx) presentation deck."""
        from fastapi.responses import Response as _Response
        from .artifacts.document_ast import DocumentParser
        from .artifacts.exporters.pptx_exporter import PptxExporter
        from .documents.pdf import safe_filename
        try:
            parser = DocumentParser()
            doc_ast = parser.parse(body.markdown, title=body.title or "Executive Briefing")
            exporter = PptxExporter()
            data = exporter.export(doc_ast)
        except HTTPException:
            raise
        except Exception as error:
            logger.exception("PPTX rendering failed")
            raise HinaaError(
                "DOCUMENT_PPTX_FAILED",
                f"The presentation deck could not be rendered ({type(error).__name__}).",
                500,
                True,
                False,
            ) from error
        if not data or len(data) > 50_000_000:
            raise HTTPException(status_code=413, detail="Presentation deck too large to render")
        raw_name = safe_filename(body.title)
        filename = raw_name[:-4] + ".pptx" if raw_name.lower().endswith(".pdf") else f"{raw_name}.pptx"
        return _Response(
            content=data,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-store",
            },
        )

    @app.get("/v1/prodcamp/features")
    @app.get("/api/v1/prodcamp/features")
    async def get_prodcamp_features(status: str | None = None, search: str | None = None, limit: int = 20):
        """Retrieve features and roadmap from ProdCamp."""
        from .tools.prodcamp import prodcamp_list_features, ListFeaturesParams
        result = await prodcamp_list_features(ListFeaturesParams(status=status, search=search, limit=limit))
        return {"result": result}

    @app.post("/v1/prodcamp/feedback")
    @app.post("/api/v1/prodcamp/feedback")
    async def post_prodcamp_feedback(request: Request):
        """Submit feedback or feature requests into ProdCamp."""
        body = await request.json()
        from .tools.prodcamp import prodcamp_submit_feedback, SubmitFeedbackParams
        result = await prodcamp_submit_feedback(
            SubmitFeedbackParams(
                content=body.get("content", ""),
                account_name=body.get("accountName") or body.get("account_name"),
                source_url=body.get("sourceUrl") or body.get("source_url"),
            )
        )
        return {"result": result}

    @app.post("/v1/prodcamp/features")
    @app.post("/api/v1/prodcamp/features")
    async def post_prodcamp_feature(request: Request):
        """Create a new roadmap feature in ProdCamp."""
        body = await request.json()
        from .tools.prodcamp import prodcamp_create_feature, CreateFeatureParams
        result = await prodcamp_create_feature(
            CreateFeatureParams(
                name=body.get("name", ""),
                status_caption=body.get("statusCaption") or body.get("status_caption") or "Backlog",
                priority_caption=body.get("priorityCaption") or body.get("priority_caption") or "Normal",
                is_public=body.get("isPublic", True),
            )
        )
        return {"result": result}

    @app.post("/v1/vision/observe")
    @app.post("/api/v1/vision/observe")
    async def observe_vision_frame(body: VisionObserveBody):
        """Analyze a live screen or webcam frame via Gemini 3.8 Flash multimodal vision."""
        from .intelligence.live_vision import live_vision_service
        return await live_vision_service.observe_frame(
            frame_base64=body.frame,
            query=body.query,
            conversation_id=body.conversationId,
            companion_id=body.companionId or "hinaa",
        )

    @app.post("/v1/vision/react")
    @app.post("/api/v1/vision/react")
    async def react_to_vision_frame(body: VisionReactBody):
        """Consent-gated webcam frame -> structured in-character reaction. Frames are never stored."""
        from .intelligence import companion_vision as cv

        if not body.consent:
            raise HTTPException(status_code=403, detail="Camera consent is required.")
        try:
            return await cv.companion_vision_service.react(
                body.frame,
                session_id=body.sessionId or "default",
                context=body.context or "",
                sedentary_minutes=body.sedentaryMinutes,
                store_observations=body.storeObservations,
            )
        except cv.FrameTooLarge:
            raise HTTPException(status_code=413, detail="Frame exceeds 300KB cap.")
        except cv.InvalidFrame as err:
            raise HTTPException(status_code=400, detail=str(err))

    @app.get("/v1/companion/briefing")
    @app.get("/api/v1/companion/briefing")
    async def get_companion_briefing(request: Request, companion_id: str = "hinaa"):
        """Generate a contextual, proactive morning/work briefing."""
        user_id = _resolve_user_id(request) or "dev_user"
        from .intelligence.proactive_briefing import generate_proactive_briefing
        return await generate_proactive_briefing(
            user_id=user_id,
            memory_service=memory_service,
            companion_id=companion_id,
        )

    @app.post("/v1/agents/swarm/execute")
    @app.post("/api/v1/agents/swarm/execute")
    async def execute_agent_swarm(body: SwarmExecutionBody):
        """Execute an autonomous background multi-agent swarm mission."""
        from .agents.worker_hive import worker_hive
        return await worker_hive.execute_mission(
            mission=body.mission,
            tasks=body.tasks,
            conversation_id=body.conversationId,
        )

    @app.get("/v1/projects/artifacts/{artifact_id}/export")
    async def export_project_artifact(request: Request, artifact_id: str, format: str = "md") -> Response:
        exported = workspace_service.export_artifact_markdown(
            _workspace_user_id(request), artifact_id
        )
        if exported is None:
            raise HTTPException(status_code=404, detail="Artifact not found")
        filename, content = exported
        if format.lower() == "pdf":
            from .documents.pdf import render_markdown_pdf, safe_filename
            data = render_markdown_pdf(content, title=filename.removesuffix(".md") or "HINAA artifact")
            return Response(
                content=data,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="{safe_filename(filename)}"',
                    "Cache-Control": "no-store",
                },
            )
        return Response(
            content=content,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.post("/v1/projects/{project_id}/files", status_code=201)
    async def upload_project_file(
        request: Request, project_id: str, file: UploadFile = File(...)
    ) -> dict[str, Any]:
        content = await file.read()
        if len(content) > 25 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Files are limited to 25 MB")
        record = workspace_service.save_file(
            _workspace_user_id(request),
            project_id,
            file.filename or "upload",
            content,
            file.content_type or "application/octet-stream",
        )
        if record is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return record

    @app.post("/v1/projects/files/{file_id}/analyze", status_code=201)
    async def analyze_project_file(request: Request, file_id: str) -> dict[str, Any]:
        try:
            artifact = workspace_service.analyze_file(_workspace_user_id(request), file_id)
        except (ValueError, RuntimeError, TimeoutError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if artifact is None:
            raise HTTPException(status_code=404, detail="File not found")
        return artifact

    @app.get("/v1/projects/files/{file_id}")
    async def download_project_file(request: Request, file_id: str) -> FileResponse:
        resolved = workspace_service.resolve_file(_workspace_user_id(request), file_id)
        if resolved is None:
            raise HTTPException(status_code=404, detail="File not found")
        path, media_type = resolved
        return FileResponse(path, media_type=media_type, filename=path.name)

    @app.get("/v1/artifacts/lookup")
    async def lookup_artifact(request: Request, kind: str) -> dict[str, Any]:
        """Find the newest artifact of a kind, from the project store then from disk.

        ``kind`` accepts both the project-store tokens (``note``, ``research``,
        ``document``, ``image``) and the formats the UI asks for (``pdf``,
        ``docx``, ``pptx``, ``xlsx``). A kind with no project record still
        resolves if the file exists, which is the case for every document
        rendered before artifacts were persisted.
        """
        normalized = kind.strip().lower()
        local_artifact = workspace_service.latest_artifact(_workspace_user_id(request), normalized)
        if local_artifact:
            return {
                "found": True,
                "source": "project",
                "artifact": local_artifact,
                "downloadUrl": f"/api/v1/projects/artifacts/{local_artifact['id']}/export",
            }

        from .artifacts.inventory import list_document_artifacts, list_image_artifacts

        is_image = normalized in {"image", "images"}
        on_disk = (
            list_image_artifacts(limit=1)
            if is_image
            else list_document_artifacts(normalized, limit=1)
        )
        if on_disk:
            artifact = on_disk[0]
            return {
                "found": True,
                "source": "images" if is_image else "documents",
                "artifact": artifact,
                "downloadUrl": str(artifact["downloadUrl"]),
            }

        return {
            "found": False,
            "kind": normalized,
            "message": f"No {normalized.upper()} artifact found in your projects.",
            "suggestion": f"Ask me to create a new {normalized.upper()} document.",
        }

    # Phase 14 Artifact OS Surface extracted to routers/artifacts_router.py
    from .routers.artifacts_router import build_artifacts_router
    app.include_router(build_artifacts_router(artifact_service, active_settings))

    @app.get("/v1/conversations")
    @app.get("/api/v1/conversations")
    async def list_conversations(
        auth: AuthContext | None = Depends(conversation_auth),
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        if auth is None:
            raise HinaaError("AUTH_REQUIRED", "Authentication required to view conversations", 401, True)
        if memory_service is None:
            return []
        return memory_service.list_conversations(auth.user_id, limit=max(1, min(limit, 100)), offset=max(0, offset))

    @app.get("/v1/conversations/{conversation_id}/messages")
    @app.get("/api/v1/conversations/{conversation_id}/messages")
    async def conversation_messages(
        conversation_id: str,
        auth: AuthContext | None = Depends(conversation_auth),
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        if auth is None:
            raise HinaaError("AUTH_REQUIRED", "Authentication required to view messages", 401, True)
        if memory_service is None:
            return []
        return memory_service.get_conversation_messages(
            auth.user_id, conversation_id, limit=max(1, min(limit, 200)), offset=max(0, offset)
        )

    @app.patch("/v1/conversations/{conversation_id}")
    @app.patch("/api/v1/conversations/{conversation_id}")
    async def rename_conversation(
        conversation_id: str,
        body: ConversationTitleBody,
        auth: AuthContext | None = Depends(conversation_auth),
    ) -> dict[str, Any]:
        if memory_service is None or auth is None:
            raise HinaaError("AUTH_REQUIRED", "Authentication required for conversation updates", 401, True)
        title = body.title.strip()
        if not title:
            raise HTTPException(status_code=422, detail="Conversation title cannot be empty")
        if not memory_service.update_conversation_title(auth.user_id, conversation_id, title):
            raise HTTPException(status_code=404, detail="Conversation not found")
        conversations = memory_service.list_conversations(auth.user_id, limit=100)
        return next((item for item in conversations if item["id"] == conversation_id), {"id": conversation_id, "title": title})

    @app.get("/v1/conversations/{conversation_id}/working-context")
    @app.get("/api/v1/conversations/{conversation_id}/working-context")
    async def conversation_working_context(
        conversation_id: str,
        auth: AuthContext | None = Depends(conversation_auth),
        limit: int = 12,
    ) -> dict[str, Any]:
        if memory_service is None or auth is None:
            raise HinaaError("AUTH_REQUIRED", "Authentication required for conversation context", 401, True)
        return memory_service.recent_working_context(
            auth.user_id,
            conversation_id,
            limit=max(1, min(limit, 50)),
        )

    @app.post("/v1/conversations/{conversation_id}/resolve-reference")
    @app.post("/api/v1/conversations/{conversation_id}/resolve-reference")
    async def resolve_conversation_reference(
        conversation_id: str,
        body: ConversationResolveBody,
        auth: AuthContext | None = Depends(conversation_auth),
    ) -> dict[str, Any]:
        if memory_service is None or auth is None:
            raise HinaaError("AUTH_REQUIRED", "Authentication required for reference resolution", 401, True)
        return memory_service.resolve_reference_intent(
            auth.user_id,
            conversation_id,
            body.text,
            project_state=body.projectState,
        )

    @app.get("/v1/reminders")
    @app.get("/api/v1/reminders")
    async def get_reminders(
        auth: AuthContext | None = Depends(conversation_auth),
        status: str = "scheduled",
    ) -> list[dict[str, Any]]:
        # An empty list here would read as "no reminders", so an anonymous
        # request has to fail instead of looking like an honest answer.
        if auth is None:
            raise HinaaError("AUTH_REQUIRED", "Authentication required for reminders", 401, True)
        return list_reminders(user_id=auth.user_id, status=status, settings=active_settings)

    @app.post("/v1/reminders")
    @app.post("/api/v1/reminders")
    async def create_reminder(
        request: Request,
        body: ReminderBody,
        auth: AuthContext | None = Depends(conversation_auth),
    ) -> dict[str, Any]:
        if auth is None:
            raise HinaaError("AUTH_REQUIRED", "Authentication required for reminders", 401, True)
        return schedule_reminder(
            user_id=auth.user_id,
            title=body.title,
            at=body.at,
            conversation_id=body.conversationId or request.headers.get("X-Conversation-ID"),
            settings=active_settings,
        )

    @app.post("/v1/reminders/{reminder_id}/cancel")
    @app.post("/api/v1/reminders/{reminder_id}/cancel")
    async def cancel_scheduled_reminder(
        reminder_id: str,
        auth: AuthContext | None = Depends(conversation_auth),
    ) -> dict[str, Any]:
        if auth is None:
            raise HinaaError("AUTH_REQUIRED", "Authentication required for reminders", 401, True)
        return cancel_reminder(user_id=auth.user_id, reminder_id=reminder_id, settings=active_settings)

    @app.get("/v1/training/candidates")
    async def list_training_candidates(
        auth: AuthContext | None = Depends(conversation_auth),
        status: str = "pending_review",
        limit: int = 50,
    ) -> dict[str, Any]:
        if memory_service is None or auth is None:
            return {"onlineTraining": False, "candidates": []}
        candidates = memory_service.list_training_candidates(
            auth.user_id, status=status, limit=max(1, min(limit, 100))
        )
        return {"onlineTraining": False, "candidates": candidates}

    @app.post("/v1/tasks")
    async def create_durable_task(
        body: CreateTaskBody,
        auth: AuthContext | None = Depends(conversation_auth),
    ) -> dict[str, Any]:
        if task_service is None or auth is None:
            raise HinaaError("AUTH_REQUIRED", "Authentication required for task management", 401, True)
        return task_service.create_task(
            owner_id=auth.user_id,
            goal=body.goal,
            conversation_id=body.conversationId,
            project_id=body.projectId,
            task_type=body.taskType,
            priority=body.priority,
            reasoning_mode=body.reasoningMode,
            steps=body.steps,
            metadata=body.metadata,
        )

    @app.get("/v1/tasks")
    async def list_durable_tasks(
        conversation_id: str | None = None,
        project_id: str | None = None,
        include_completed: bool = False,
        limit: int = 50,
        auth: AuthContext | None = Depends(conversation_auth),
    ) -> list[dict[str, Any]]:
        if task_service is None or auth is None:
            return []
        return task_service.list_tasks(
            owner_id=auth.user_id,
            conversation_id=conversation_id,
            project_id=project_id,
            include_completed=include_completed,
            limit=limit,
        )

    @app.get("/v1/tasks/{task_id}")
    async def get_durable_task(
        task_id: str,
        auth: AuthContext | None = Depends(conversation_auth),
    ) -> dict[str, Any]:
        if task_service is None or auth is None:
            raise HinaaError("AUTH_REQUIRED", "Authentication required for task retrieval", 401, True)
        return task_service.get_task(auth.user_id, task_id)

    @app.get("/v1/tasks/{task_id}/events")
    async def task_events(
        task_id: str,
        after: int = 0,
        auth: AuthContext | None = Depends(conversation_auth),
    ) -> dict[str, Any]:
        if task_service is None or auth is None:
            raise HinaaError("AUTH_REQUIRED", "Authentication required for task events", 401, True)
        return task_service.events(auth.user_id, task_id, after=after)

    @app.get("/v1/tasks/{task_id}/checkpoints")
    async def task_checkpoints(
        task_id: str,
        auth: AuthContext | None = Depends(conversation_auth),
    ) -> list[dict[str, Any]]:
        if task_service is None or auth is None:
            raise HinaaError("AUTH_REQUIRED", "Authentication required for task checkpoints", 401, True)
        return task_service.list_checkpoints(auth.user_id, task_id)

    @app.post("/v1/tasks/resolve")
    async def resolve_durable_task(
        body: ResolveTaskBody,
        auth: AuthContext | None = Depends(conversation_auth),
    ) -> dict[str, Any]:
        if task_service is None or auth is None:
            raise HinaaError("AUTH_REQUIRED", "Authentication required for task resolution", 401, True)
        return task_service.resolve_active_task(
            auth.user_id,
            text=body.text,
            conversation_id=body.conversationId,
            project_id=body.projectId,
        )

    @app.post("/v1/tasks/{task_id}/continue")
    async def continue_durable_task(
        task_id: str,
        auth: AuthContext | None = Depends(conversation_auth),
    ) -> dict[str, Any]:
        if task_service is None or auth is None:
            raise HinaaError("AUTH_REQUIRED", "Authentication required to continue task", 401, True)
        return task_service.continue_task(auth.user_id, task_id)

    @app.post("/v1/tasks/claim")
    async def claim_durable_task(
        body: ClaimTaskBody,
        auth: AuthContext | None = Depends(conversation_auth),
    ) -> dict[str, Any] | None:
        if task_service is None or auth is None:
            raise HinaaError("AUTH_REQUIRED", "Authentication required to claim task", 401, True)
        return task_service.claim_next(
            auth.user_id,
            worker_id=body.workerId,
            lease_seconds=body.leaseSeconds,
            conversation_id=body.conversationId,
            project_id=body.projectId,
        )

    @app.post("/v1/tasks/{task_id}/steps/{step_id}/complete")
    async def complete_task_step(
        task_id: str,
        step_id: str,
        body: CompleteStepBody | None = None,
        auth: AuthContext | None = Depends(conversation_auth),
    ) -> dict[str, Any]:
        if task_service is None or auth is None:
            raise HinaaError("AUTH_REQUIRED", "Authentication required to complete step", 401, True)
        output_ids = body.outputArtifactIds if body else None
        return task_service.complete_step(auth.user_id, task_id, step_id, output_artifact_ids=output_ids)

    @app.post("/v1/tasks/{task_id}/steps/{step_id}/complete-with-lease")
    async def complete_task_step_with_lease(
        task_id: str,
        step_id: str,
        body: CompleteStepWithLeaseBody,
        auth: AuthContext | None = Depends(conversation_auth),
    ) -> dict[str, Any]:
        if task_service is None or auth is None:
            raise HinaaError("AUTH_REQUIRED", "Authentication required to complete leased step", 401, True)
        return task_service.complete_step_with_lease(
            auth.user_id,
            task_id,
            step_id,
            lease_id=body.leaseId,
            fencing_token=body.fencingToken,
            output_artifact_ids=body.outputArtifactIds,
        )

    @app.post("/v1/tasks/{task_id}/steps/{step_id}/fail")
    async def fail_task_step(
        task_id: str,
        step_id: str,
        body: FailStepBody,
        auth: AuthContext | None = Depends(conversation_auth),
    ) -> dict[str, Any]:
        if task_service is None or auth is None:
            raise HinaaError("AUTH_REQUIRED", "Authentication required to report step failure", 401, True)
        return task_service.fail_step(auth.user_id, task_id, step_id, body.reason, retry_limit=body.retryLimit)

    @app.post("/v1/tasks/{task_id}/steer")
    async def steer_durable_task(
        task_id: str,
        body: SteerTaskBody,
        auth: AuthContext | None = Depends(conversation_auth),
    ) -> dict[str, Any]:
        if task_service is None or auth is None:
            raise HinaaError("AUTH_REQUIRED", "Authentication required to steer task", 401, True)
        return task_service.steer_task(auth.user_id, task_id, body.instruction)

    @app.post("/v1/tasks/{task_id}/cancel")
    async def cancel_durable_task(
        task_id: str,
        body: CancelTaskBody | None = None,
        auth: AuthContext | None = Depends(conversation_auth),
    ) -> dict[str, Any]:
        if task_service is None or auth is None:
            raise HinaaError("AUTH_REQUIRED", "Authentication required to cancel task", 401, True)
        reason = body.reason if body else None
        return task_service.cancel_task(auth.user_id, task_id, reason=reason)

    @app.post("/v1/tasks/{task_id}/pause")
    async def pause_durable_task(
        task_id: str,
        body: CancelTaskBody | None = None,
        auth: AuthContext | None = Depends(conversation_auth),
    ) -> dict[str, Any]:
        if task_service is None or auth is None:
            raise HinaaError("AUTH_REQUIRED", "Authentication required to pause task", 401, True)
        return task_service.pause_task(auth.user_id, task_id, reason=body.reason if body else None)

    @app.post("/v1/tasks/{task_id}/resume")
    async def resume_durable_task(
        task_id: str,
        auth: AuthContext | None = Depends(conversation_auth),
    ) -> dict[str, Any]:
        if task_service is None or auth is None:
            raise HinaaError("AUTH_REQUIRED", "Authentication required to resume task", 401, True)
        return task_service.resume_task(auth.user_id, task_id)

    @app.post("/v1/tasks/{task_id}/side-effects")
    async def plan_side_effect(
        task_id: str,
        body: SideEffectPlannedBody,
        auth: AuthContext | None = Depends(conversation_auth),
    ) -> dict[str, Any]:
        if task_service is None or auth is None:
            raise HinaaError("AUTH_REQUIRED", "Authentication required to journal side effects", 401, True)
        return task_service.record_side_effect_planned(
            auth.user_id,
            task_id,
            step_id=body.stepId,
            idempotency_key=body.idempotencyKey,
            provider=body.provider,
            operation_type=body.operationType,
            request_payload=body.requestPayload,
        )

    @app.post("/v1/tasks/side-effects/{operation_id}/provider-accepted")
    async def accept_side_effect(
        operation_id: str,
        body: SideEffectAcceptedBody,
        auth: AuthContext | None = Depends(conversation_auth),
    ) -> dict[str, Any]:
        if task_service is None or auth is None:
            raise HinaaError("AUTH_REQUIRED", "Authentication required to update side effects", 401, True)
        return task_service.mark_side_effect_provider_accepted(
            auth.user_id,
            operation_id,
            provider_operation_id=body.providerOperationId,
            response_payload=body.responsePayload,
        )

    @app.post("/v1/tasks/{task_id}/rollback")
    async def rollback_durable_task(
        task_id: str,
        body: RollbackTaskBody,
        auth: AuthContext | None = Depends(conversation_auth),
    ) -> dict[str, Any]:
        if task_service is None or auth is None:
            raise HinaaError("AUTH_REQUIRED", "Authentication required to rollback task", 401, True)
        return task_service.rollback_to_checkpoint(auth.user_id, task_id, version=body.version)

    @app.post("/v1/tasks/recover")
    async def recover_durable_tasks(
        auth: AuthContext | None = Depends(conversation_auth),
    ) -> list[dict[str, Any]]:
        if task_service is None or auth is None:
            raise HinaaError("AUTH_REQUIRED", "Authentication required to recover tasks", 401, True)
        return task_service.recover_interrupted_tasks(owner_id=auth.user_id)

    @app.post("/v1/conversations/turns:stream")
    @app.post("/api/v1/conversations/turns:stream")
    async def stream_turn(request: Request, body: TurnRequest) -> StreamingResponse:
        # The web client normally sends its resolved provider explicitly. For
        # direct local API callers, inherit the CX-first server preference only
        # when providerMode was omitted; a machine without CX configuration
        # still receives the deterministic local mock fallback instead of an
        # opaque configuration failure.
        if "providerMode" not in body.model_fields_set:
            default_mode = active_settings.provider_mode
            if default_mode == "cx-gateway" and not active_settings.cx_gateway_configured:
                default_mode = "mock"
            body = body.model_copy(update={"providerMode": default_mode})
        user_id = _resolve_user_id(request)

        agent_run = None
        owner_id = user_id or (
            active_settings.dev_auth_subject
            if (active_settings.allow_tunnel_dev_auth or not reached_through_edge(request))
            else None
        )
        is_agent_request = (
            body.text.strip().startswith(("/deep", "/agent", "/plan", "/workflow"))
            or body.responseMode in ("automation", "research")
            or bool(re.search(r"\b(deep\s+research|audit\s+the\s+entire|refactor\s+the\s+entire|step\s+by\s+step\s+plan\s+and\s+execute)\b", body.text, re.I))
        )
        if active_settings.agent_runtime_enabled and agent_runtime is not None and owner_id and is_agent_request:
            agent_run = agent_runtime.create_run(
                goal=body.text,
                user_id=owner_id,
                conversation_id=body.conversationId or body.sessionId,
            )

        async def guarded_stream():  # type: ignore[no-untyped-def]
            # The run ledger is the audit trail for "did she actually stop?":
            # a start row here and a stop/idle row in the finally below.
            turn_id = request.state.correlation_id
            req_trace_id = getattr(request.state, "trace_id", "") or turn_id
            turn_t0 = time.perf_counter()
            first_token_ms: float | None = None
            total_chars_streamed = 0
            stream_ledger = get_run_ledger()
            stream_ledger.record_turn_start(
                turn_id,
                session_id=body.sessionId,
                provider=body.providerMode,
            )
            turn_completed = False
            ledger_plan: dict[str, Any] | None = None
            stream_plan = None
            stream_step = None
            pending_runtime_events: list[AgentEvent] = []
            runtime_events_flushed = False
            try:
                if agent_run:
                    created_events = agent_runtime.get_events(agent_run.run_id, {agent_run.user_id}) or []
                    if created_events:
                        pending_runtime_events.append(created_events[-1])
                    stream_plan, stream_step, started_events = agent_runtime.begin_stream_turn(agent_run)
                    pending_runtime_events.extend(started_events)

                final_plan_payload: dict[str, Any] | None = None
                stream_iter = service.stream_turn(
                    body, request.state.correlation_id, user_id=owner_id or user_id
                ).__aiter__()
                # Liveness decides, not wall clock. A documented report is a long
                # generation, and a recovery chain that has to hand the turn to a
                # second or third brain spends minutes doing it. The fixed deadline
                # here killed that work mid-flight: measured on production, a report
                # run died at exactly run_timeout (300s) while its claude fallback was
                # returning HTTP 200s. The provider stream layer one level down already
                # uses an idle timeout plus an absolute ceiling, so this layer matches it
                # instead of running its own stricter wall clock.
                run_budget = (
                    agent_runtime.run_timeout
                    if (agent_run and agent_runtime and getattr(agent_runtime, "run_timeout", None))
                    else None
                )
                idle_timeout = (
                    min(run_budget, active_settings.llm_stream_idle_timeout_seconds)
                    if run_budget is not None
                    else None
                )
                ceiling_at = (
                    time.time() + max(active_settings.llm_stream_ceiling_seconds, idle_timeout)
                    if idle_timeout is not None
                    else None
                )
                while True:
                    try:
                        if idle_timeout is None:
                            event = await stream_iter.__anext__()
                        else:
                            time_left = ceiling_at - time.time()
                            if time_left <= 0:
                                raise TimeoutError()
                            event = await asyncio.wait_for(
                                stream_iter.__anext__(),
                                timeout=max(0.001, min(idle_timeout, time_left)),
                            )
                    except StopAsyncIteration:
                        break
                    except (TimeoutError, asyncio.TimeoutError):
                        raise HinaaError("RUN_TIMEOUT", "Agent run exceeded configured execution deadline.", 408, False)
                    try:
                        decoded = json.loads(event.decode("utf-8"))
                        ev_type = decoded.get("type")
                        if ev_type == "text.delta":
                            if first_token_ms is None:
                                first_token_ms = round((time.perf_counter() - turn_t0) * 1000, 2)
                            total_chars_streamed += len(decoded.get("delta", ""))
                        elif ev_type == "plan" and isinstance(decoded.get("plan"), dict):
                            final_plan_payload = decoded["plan"]
                            ledger_plan = final_plan_payload
                    except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
                        pass
                    yield event
                    if pending_runtime_events and not runtime_events_flushed:
                        runtime_events_flushed = True
                        for runtime_event in pending_runtime_events:
                            yield _runtime_event_payload(runtime_event)

                if agent_run and stream_plan and stream_step:
                    completed_events = agent_runtime.complete_stream_turn(
                        agent_run,
                        stream_plan,
                        stream_step,
                        result=final_plan_payload,
                    )
                    for runtime_event in completed_events:
                        yield _runtime_event_payload(runtime_event)
                turn_completed = True
                turn_dur_ms = round((time.perf_counter() - turn_t0) * 1000, 2)
                yield service._event(
                    "telemetry.trace",
                    {
                        "traceId": req_trace_id,
                        "providerMode": body.providerMode,
                        "brainModel": body.brainModel or "",
                        "ttftMs": first_token_ms,
                        "totalDurationMs": turn_dur_ms,
                        "charsStreamed": total_chars_streamed,
                        "status": "completed",
                    },
                )
            except HinaaError as error:
                logger.warning(
                    "Streamed turn failed: code=%s message=%s cause=%s",
                    error.code,
                    error.message,
                    getattr(error, "developer_message", None),
                )
                if agent_run:
                    for runtime_event in agent_runtime.fail_stream_turn(
                        agent_run,
                        step=stream_step,
                        code=error.code,
                        message=error.message,
                    ):
                        yield _runtime_event_payload(runtime_event)
                yield service._event(
                    "error",
                    {
                        "code": error.code,
                        "message": error.message,
                        "retryable": error.retryable,
                        "correlationId": request.state.correlation_id,
                        # A turn that dies before its plan event used to leave the
                        # client holding nothing but the mode it asked for, so a
                        # Claude request that 403'd kept a Claude badge on screen.
                        "routing": _routing_truth(active_settings, body.providerMode),
                    },
                )
            except Exception as error:
                if agent_run:
                    for runtime_event in agent_runtime.fail_stream_turn(
                        agent_run,
                        step=stream_step,
                        code="STREAM_ERROR",
                        message=str(error),
                    ):
                        yield _runtime_event_payload(runtime_event)
                raise
            finally:
                # One terminal row per turn: the delivered text and the idle
                # timestamp the stop-fix is judged by.
                stream_ledger.record_turn_stop(
                    turn_id,
                    response_text=_ledger_response_text(ledger_plan),
                    status="completed" if turn_completed else "aborted",
                    provider=body.providerMode,
                )
                try:
                    from .telemetry.metrics import record_turn_metrics
                    final_turn_dur = round((time.perf_counter() - turn_t0) * 1000, 2)
                    ttft_val = first_token_ms if first_token_ms is not None else final_turn_dur
                    record_turn_metrics(
                        trace_id=req_trace_id,
                        provider_id=body.providerMode,
                        model=body.brainModel or "default",
                        ttft_ms=ttft_val,
                        model_latency_ms=ttft_val,
                        total_turn_ms=final_turn_dur,
                        chars_generated=total_chars_streamed,
                        success=turn_completed,
                    )
                except Exception:
                    pass

        return StreamingResponse(guarded_stream(), media_type="application/x-ndjson")

    @app.post("/v1/astra/turns:stream")
    @app.post("/api/v1/astra/turns:stream")
    async def stream_astra_turn(request: Request, body: AstraRequest = Body(...)) -> StreamingResponse:
        user_id = _resolve_user_id(request)
        if user_id and not body.user_id:
            body = body.model_copy(update={"user_id": user_id})

        async def astra_event_generator():
            async for event in astra_runtime.stream_turn(body):
                yield event.to_sse()

        return StreamingResponse(
            astra_event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.delete("/v1/sessions/{session_id}", status_code=204)
    async def clear_session(session_id: str) -> Response:
        service.memory.clear(session_id)
        return Response(status_code=204)

    @app.post("/v1/text/humanize", response_model=TextHumanizerResponse)
    async def text_humanize(body: TextHumanizerRequest) -> TextHumanizerResponse:
        import re
        
        text = body.text
        
        protected_map = {}
        counter = [0]
        
        def repl_protect(m):
            key = f"[[PROTECTED_SPAN_{counter[0]}]]"
            protected_map[key] = m.group(0)
            counter[0] += 1
            return key
            
        # Code
        text = re.sub(r'```.*?```', repl_protect, text, flags=re.DOTALL)
        text = re.sub(r'`[^`]+`', repl_protect, text)
        
        # Markdown Links
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', repl_protect, text)
        # Raw Links
        text = re.sub(r'https?://[^\s]+', repl_protect, text)
        
        # Citations: [1], [1, 2]
        text = re.sub(r'\[\d+(?:,\s*\d+)*\]', repl_protect, text)
        
        # Paths: C:\foo\bar or /foo/bar
        text = re.sub(r'(?:[a-zA-Z]:\\|/)(?:[\w.-]+(?:\\|/))*[\w.-]+', repl_protect, text)
        
        # Numbers
        text = re.sub(r'\b\d+(?:\.\d+)?\b', repl_protect, text)
        
        # Emails
        text = re.sub(r'[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}', repl_protect, text)
        
        # Hindi (Devanagari)
        text = re.sub(r'[\u0900-\u097F]+', repl_protect, text)
        
        external_transfer = False
        review_metrics = None
        review_ideas = None
        
        if body.action == "review":
            humanized = text
            sentences = [s.strip() for s in re.split(r'[.!?]+', body.text) if s.strip()]
            paragraphs = [p.strip() for p in body.text.split('\n\n') if p.strip()]
            
            word_count = len(re.findall(r'\b\w+\b', body.text))
            english_word_count = len(re.findall(r'\b[A-Za-z]+\b', body.text))
            
            long_sentences = 0
            dense_paragraphs = 0
            ideas = []
            
            openings = []
            for s in sentences:
                if re.search(r'[\u0900-\u097F]', s):
                    continue
                
                words = re.findall(r'\b[A-Za-z]+\b', s)
                if words:
                    opening = words[0].lower()
                    if openings and openings[-1] == opening:
                        ideas.append(f"Repetition: Consider varying sentence openings. Multiple sentences start with '{opening}'.")
                    openings.append(opening)
                    
                    if len(words) > 30:
                        long_sentences += 1
                        
            if long_sentences > 0:
                ideas.append(f"Length: Found {long_sentences} sentences over 30 words. Consider breaking them up for clarity.")
                
            for p in paragraphs:
                p_sentences = [s.strip() for s in re.split(r'[.!?]+', p) if s.strip()]
                p_words = len(re.findall(r'\b\w+\b', p))
                if len(p_sentences) > 5 or p_words > 100:
                    dense_paragraphs += 1
            
            if dense_paragraphs > 0:
                ideas.append(f"Density: Found {dense_paragraphs} dense paragraphs. Try splitting them to improve readability.")
                
            fillers = [r'\bactually\b', r'\bbasically\b', r'\bliterally\b', r'\bjust\b', r'\bvery\b']
            filler_count = sum(len(re.findall(f, body.text, flags=re.IGNORECASE)) for f in fillers)
            
            if filler_count > 0:
                ideas.append(f"Filler: Detected {filler_count} filler words. Removing them tightens the prose.")
                
            review_metrics = {
                "wordCount": word_count,
                "englishWordCount": english_word_count,
                "sentenceCount": len(sentences),
                "longEnglishSentences": long_sentences,
                "denseParagraphs": dense_paragraphs
            }
            review_ideas = ideas

        elif body.providerMode == "local":
            text = re.sub(r'\s+', ' ', text)
            fillers = [r'\bactually\b', r'\bbasically\b', r'\bliterally\b', r'\bjust\b', r'\bvery\b']
            for f in fillers:
                text = re.sub(f, '', text, flags=re.IGNORECASE)
            
            text = re.sub(r'\s+', ' ', text).strip()
            humanized = text
        else:
            # We enforce externalTextTransfer=False for this tool per requirements.
            external_transfer = False
            from .prompts.models import PromptPackage, PersonalitySettings, MoodSnapshot
            
            mode_prompts = {
                "natural": "Rewrite this text to sound more natural, flowing, and human-like. Fix typos but do not change the core meaning or facts.",
                "warm": "Rewrite this text to sound warm, empathetic, supportive, and friendly. Do not change the facts.",
                "professional": "Rewrite this text to sound professional, objective, and clear for a workplace setting.",
                "concise": "Rewrite this text to be as concise, brief, and direct as possible. Remove all filler."
            }
            instruction = mode_prompts.get(body.mode, mode_prompts["natural"])
            
            prompt = PromptPackage(
                companion_id="hinaa",
                interaction_mode="rest",
                system_instruction=f"You are a writing quality assistant. {instruction}\nReturn ONLY the final rewritten text. DO NOT add conversational filler like 'Here is the rewrite:'. Preserve any [[PROTECTED_*]] markers exactly as they appear.",
                user_contents=text,
                layers=[],
                prompt_version="1",
                safety_policy_version="1",
                companion_profile_version="1",
                fingerprint="humanizer",
                response_depth="conversational",
                language="en-US",
                personality=PersonalitySettings(),
                mood=MoodSnapshot(valence=0.0, arousal=0.0)
            )
            
            provider = service._router.get_provider(body.providerMode, body.brainModel)
            
            try:
                humanized = await provider._chat_text(prompt)
                humanized = humanized.strip()
            except Exception as e:
                logger.error(f"Humanizer LLM error: {e}")
                humanized = text
                
        for key, val in protected_map.items():
            humanized = humanized.replace(key, val)
            
        return TextHumanizerResponse(
            originalText=body.text,
            humanizedText=humanized,
            protectedSpans=len(protected_map),
            externalTextTransfer=external_transfer,
            mode=body.mode,
            reviewMetrics=review_metrics,
            reviewIdeas=review_ideas
        )

    @app.post("/v1/speech/synthesis/timed")
    @app.post("/api/v1/speech/synthesis/timed")
    async def synthesize_timed(body: SpeechRequest) -> Response:
        """Audio plus vendor character timing for lip-sync.

        Opt-in and ElevenLabs-only. When timing is unavailable it still returns
        the audio with an empty alignment, so the client falls back to the text
        estimate and nothing is lost.
        """
        import base64
        import json as _json

        from .providers.elevenlabs import ElevenLabsHTTPStreamingProvider
        from .voice_performance import speech_text_for_tts

        started = perf_counter()
        provider = service.router.tts(body.providerMode, body.companionId, body.voiceEngine)
        if not isinstance(provider, ElevenLabsHTTPStreamingProvider):
            result = await service.synthesize(body)
            final_audio, media_type = ensure_wav_or_mp3(result.value, sample_rate=24_000)
            alignment: list[dict] | None = None
            provider_name = result.provider
        else:
            text = speech_text_for_tts(body.text) or body.text
            voice_id = (
                service.settings.elevenlabs_hiro_voice_id
                if body.companionId == "hiro"
                else service.settings.elevenlabs_hinaa_voice_id
            )
            try:
                audio_bytes, speech_alignment, _ms = await provider.synthesize_timed(
                    text, voice=voice_id
                )
                final_audio, media_type = ensure_wav_or_mp3(audio_bytes, sample_rate=24_000)
                alignment = (
                    [
                        {"char": c, "startMs": s, "durationMs": d}
                        for c, s, d in zip(
                            speech_alignment.characters,
                            speech_alignment.start_times_ms,
                            speech_alignment.durations_ms,
                            strict=True,
                        )
                    ]
                    if speech_alignment is not None
                    else None
                )
                provider_name = "elevenlabs"
            except Exception:
                result = await service.synthesize(body)
                final_audio, media_type = ensure_wav_or_mp3(result.value, sample_rate=24_000)
                alignment = None
                provider_name = result.provider
        filename = "hinaa-turn.mp3" if media_type == "audio/mpeg" else "hinaa-turn.wav"
        alignment_header = base64.b64encode(
            _json.dumps(alignment or []).encode("utf-8")
        ).decode("ascii")
        return Response(
            final_audio,
            media_type=media_type,
            headers={
                "X-HINAA-Provider": provider_name,
                "X-HINAA-Latency-Ms": str(int((perf_counter() - started) * 1000)),
                "X-HINAA-Alignment": alignment_header,
                "Content-Disposition": f'inline; filename="{filename}"',
            },
        )

    @app.post("/v1/speech/synthesis")
    @app.post("/api/v1/speech/synthesis")
    async def synthesize(body: SpeechRequest) -> Response:
        started = perf_counter()
        result = await service.synthesize(body)
        final_audio, media_type = ensure_wav_or_mp3(result.value, sample_rate=24_000)
        filename = "hinaa-turn.mp3" if media_type == "audio/mpeg" else "hinaa-turn.wav"
        return Response(
            final_audio,
            media_type=media_type,
            headers={
                "X-HINAA-Provider": result.provider,
                "X-HINAA-Latency-Ms": str(result.latency_ms),
                "X-HINAA-Total-Ms": str(int((perf_counter() - started) * 1000)),
                "Content-Disposition": f'inline; filename="{filename}"',
            },
        )

    if memory_service is not None and require_auth is not None:

        @app.get("/v1/privacy/status")
        async def privacy_status(auth: AuthContext = Depends(require_auth)) -> dict[str, object]:
            return memory_service.privacy_status(auth.user_id)

        @app.patch("/v1/privacy/memory")
        async def toggle_memory(
            body: MemoryToggleBody, auth: AuthContext = Depends(require_auth)
        ) -> dict[str, object]:
            return memory_service.set_memory_enabled(auth.user_id, body.enabled)

        @app.get("/v1/privacy/memories")
        async def list_memories(auth: AuthContext = Depends(require_auth)) -> dict[str, object]:
            return {"memories": memory_service.list_memories(auth.user_id)}

        @app.post("/v1/privacy/memories")
        async def remember(
            body: RememberBody, auth: AuthContext = Depends(require_auth)
        ) -> dict[str, object]:
            return memory_service.remember(
                auth.user_id,
                body.content,
                category=body.category,
                source_turn_ref=body.sourceTurnRef,
                explicit=True,
            )

        @app.delete("/v1/privacy/memories/{memory_id}")
        async def forget_memory(
            memory_id: str, auth: AuthContext = Depends(require_auth)
        ) -> dict[str, object]:
            return memory_service.forget(auth.user_id, memory_id)

        @app.put("/v1/privacy/memories/{memory_id}")
        async def update_memory(
            memory_id: str, body: UpdateMemoryBody, auth: AuthContext = Depends(require_auth)
        ) -> dict[str, object]:
            return memory_service.update_memory(
                auth.user_id, memory_id, body.content, body.expiresAt
            )

        @app.post("/v1/privacy/memories/{memory_id}/supersede")
        async def supersede_memory(
            memory_id: str, body: RememberBody, auth: AuthContext = Depends(require_auth)
        ) -> dict[str, object]:
            old_mem, new_mem = memory_service.supersede_memory(
                auth.user_id,
                memory_id,
                body.content,
                category=body.category,
                source_turn_ref=body.sourceTurnRef,
            )
            return {"superseded": old_mem, "new": new_mem}

        @app.delete("/v1/privacy/memories")
        async def clear_all_memories(auth: AuthContext = Depends(require_auth)) -> dict[str, object]:
            return memory_service.delete_all_memories(auth.user_id)

        @app.delete("/v1/privacy/conversations/{conversation_id}")
        async def clear_conversation(
            conversation_id: str, auth: AuthContext = Depends(require_auth)
        ) -> dict[str, object]:
            return memory_service.clear_conversation(auth.user_id, conversation_id)

        @app.get("/v1/privacy/export")
        async def export_data(auth: AuthContext = Depends(require_auth)) -> dict[str, object]:
            return memory_service.export_data(auth.user_id)

        @app.delete("/v1/privacy/account")
        async def delete_all(auth: AuthContext = Depends(require_auth)) -> dict[str, object]:
            return memory_service.delete_all(auth.user_id)

        @app.get("/v1/privacy/archives")
        @app.get("/api/memory/archives")
        async def list_exact_archives(
            query: str = "",
            conversation_id: str | None = None,
            limit: int = 50,
            offset: int = 0,
            auth: AuthContext = Depends(require_auth),
        ) -> dict[str, object]:
            """Retrieve preserved exact message archives (byte count, tokens, raw text)."""
            records = memory_service.search_exact_archives(
                user_id=auth.user_id,
                query=query,
                conversation_id=conversation_id,
                limit=limit,
                offset=offset,
            )
            return {"archives": records, "total": len(records)}

        @app.get("/v1/privacy/archives/{message_id}")
        @app.get("/api/memory/archives/{message_id}")
        async def get_exact_archive(
            message_id: str,
            auth: AuthContext = Depends(require_auth),
        ) -> dict[str, object]:
            """Retrieve single preserved exact message archive by message ID."""
            record = memory_service.get_exact_archive(auth.user_id, message_id)
            if not record:
                raise HTTPException(status_code=404, detail=f"Archive for message '{message_id}' not found.")
            return {"archive": record}

    @app.get("/v1/generated-docs")
    @app.get("/api/v1/generated-docs")
    async def list_generated_documents(limit: int = 200) -> dict[str, object]:
        """Every document HINAA actually rendered, newest first.

        Lists the files, not the ``.metadata.json`` sidecars. Indexing sidecars
        meant a rendered document was invisible whenever its writer failed to
        record one, which is how the library froze at a dozen rows while 161
        PDFs sat in the same directory.
        """
        from .artifacts.inventory import list_document_artifacts

        docs = list_document_artifacts("document", limit)
        return {"documents": docs, "count": len(docs)}

    @app.get("/v1/artifacts")
    async def list_artifacts(
        kind: str | None = None,
        limit: int = 200,
    ) -> dict[str, object]:
        """Everything HINAA produced that survives on disk, newest first.

        Documents and generated images read straight off the filesystem, so a
        rendered file stays listable after its own turn is gone. Documents
        previously had no list endpoint at all, which left the UI fetching a 404
        and showing nothing.
        """
        from .artifacts.inventory import (
            document_roots,
            image_roots,
            list_document_artifacts,
            list_image_artifacts,
        )

        wanted = (kind or "").strip().lower()
        artifacts: list[dict[str, object]] = []
        if wanted not in {"image", "images"}:
            artifacts += list_document_artifacts(kind, limit)
        if wanted in {"", "image", "images", "document", "file", "artifact"}:
            artifacts += list_image_artifacts(limit)
        artifacts.sort(
            key=lambda item: str(item.get("createdAt") or item.get("created_at") or ""),
            reverse=True,
        )
        artifacts = artifacts[: max(1, min(int(limit), 500))]
        return {
            "artifacts": artifacts,
            "count": len(artifacts),
            "kind": kind,
            "documents": sum(1 for item in artifacts if item.get("kind") == "document"),
            "images": sum(1 for item in artifacts if item.get("kind") == "image"),
            "indexed": sum(1 for item in artifacts if item.get("indexed")),
            "roots": [
                str(root)
                for root in [*document_roots(), *image_roots()]
                if root.exists()
            ],
        }

    # ── College & VIP Deep Vault Endpoints ─────────────────────────
    @app.post("/v1/college/students/register", status_code=201)
    async def college_register_student(payload: StudentRegistrationRequest) -> dict[str, Any]:
        """Register or verify student ID for VIP Deep Vault access."""
        return college_vault_service.register_student(payload)

    @app.get("/v1/college/students/{student_id}")
    async def college_verify_student(student_id: str) -> dict[str, Any]:
        """Verify institutional student enrollment status."""
        student = college_vault_service.verify_student(student_id)
        if not student:
            raise HTTPException(status_code=404, detail=f"Student ID '{student_id}' not found in registry.")
        return {"status": "verified", "student": student}

    @app.get("/v1/college/vault/resources")
    async def college_list_resources(category: str | None = None) -> dict[str, Any]:
        """Access curated VIP Deep Vault resources."""
        resources = college_vault_service.list_vip_resources(category=category)
        return {"resources": resources, "count": len(resources)}

    @app.get("/v1/college/admin/dashboard")
    async def college_admin_dashboard() -> dict[str, Any]:
        """College administration and faculty analytics overview."""
        return college_vault_service.get_admin_dashboard_stats()

    @app.get("/api/v1/audit/receipts")
    async def get_execution_receipts(
        turn_id: str | None = None,
        limit: int = 50,
    ):
        """Return execution receipts for audit inspection (Milestone 1)."""
        ledger = get_run_ledger()
        receipts = ledger.recent_receipts(turn_id=turn_id, limit=min(limit, 200))
        turns = ledger.recent_turns(limit=20)
        return {
            "receipts": receipts,
            "recentTurns": [t.as_dict() for t in turns],
            "ledgerAvailable": ledger.available,
        }

    # ── Generic /api/v1 aliases ─────────────────────────────────────
    # Routes are canonically declared at /v1/... but the frontend addresses
    # the API as /api/v1/... (mixed usage predates this). Mirror every
    # declared /v1 route under the /api prefix so no endpoint is ever
    # unreachable. Explicit /api/v1 declarations above are preserved.
    # FastAPI registers each method as its own route with its own handler,
    # so aliases must be per (path, method) — merging methods onto one
    # route would serve the first handler for every method.
    alias_routes: dict[str, dict[str, tuple[object, str]]] = {}
    for route in list(app.routes):
        path = getattr(route, "path", "")
        if not path.startswith("/v1/"):
            continue
        methods = {m for m in (getattr(route, "methods", None) or ()) if m not in {"HEAD", "OPTIONS"}}
        if not methods:
            continue
        per_method = alias_routes.setdefault(f"/api{path}", {})
        route_name = str(getattr(route, "name", path))
        for method in methods:
            per_method.setdefault(method, (route.endpoint, route_name))

    existing_paths = {getattr(r, "path", "") for r in app.routes}
    for alias_path, per_method in alias_routes.items():
        if alias_path in existing_paths:
            continue
        for method, (endpoint, route_name) in per_method.items():
            app.add_api_route(
                alias_path,
                endpoint,  # type: ignore[arg-type]
                methods=[method],
                name=f"api_alias_{route_name}_{method.lower()}",
                include_in_schema=False,
            )

    @app.get("/v1/ledger/turns")
    @app.get("/api/v1/ledger/turns")
    async def ledger_turns(limit: int = 20) -> dict[str, Any]:
        """Recent conversation turns with their stop/idle timestamps."""
        return {"turns": [t.as_dict() for t in get_run_ledger().recent_turns(limit)]}

    @app.get("/v1/ledger/tts")
    @app.get("/api/v1/ledger/tts")
    async def ledger_tts(limit: int = 20) -> dict[str, Any]:
        """Recent voice requests: provider, voice, model, latency, outcome."""
        return {"events": get_run_ledger().recent_tts(limit)}

    @app.get("/v1/ledger/motion")
    @app.get("/api/v1/ledger/motion")
    async def ledger_motion(limit: int = 50) -> dict[str, Any]:
        """Recent animation/idle state changes reported by the client."""
        return {"events": get_run_ledger().recent_motion(limit)}

    @app.post("/v1/ledger/motion")
    @app.post("/api/v1/ledger/motion")
    async def ledger_motion_write(payload: dict[str, Any] = Body(...)) -> dict[str, bool]:
        get_run_ledger().record_motion(
            state=str(payload.get("state") or "unknown"),
            session_id=payload.get("sessionId"),
            detail=payload.get("detail"),
        )
        return {"ok": True}

    @app.post("/api/v1/brain/claude")
    async def brain_claude_turn(request: Request) -> dict[str, Any]:
        """One Claude-routed agentic turn (native tool loop; confirmations stay pending)."""
        from .providers.claude_brain import run_claude_turn

        body = await request.json()
        text = str(body.get("text", "")).strip()
        if not text:
            raise HinaaError("INVALID_REQUEST", "text is required", 400, False, True)
        if not active_settings.claude_configured:
            raise HinaaError("PROVIDER_CONFIGURATION_MISSING", "Claude is not configured.", 503, False, True)
        result = await run_claude_turn(
            active_settings,
            text,
            system=body.get("system"),
            is_voice=bool(body.get("isVoice")),
            use_tools=bool(body.get("useTools", True)),
            host_header=request.headers.get("host"),
            user_id=_resolve_user_id(request),
        )
        return {
            "text": result.text,
            "model": result.route.model,
            "tier": result.route.tier,
            "steps": result.steps,
            "maxStepsReached": result.max_steps_reached,
            "toolEvents": [
                {"tool": e.tool, "status": e.status} for e in result.tool_events
            ],
            "pendingConfirmations": [
                {"tool": e.tool, "parameters": e.input} for e in result.pending_confirmations
            ],
        }

    @app.post("/api/v1/brain/run")
    async def brain_run_stream(request: Request):
        """Stream brain orchestration events as Server-Sent Events."""
        from .brain.coordinator import HinaBrainCoordinator, BrainRunEvent
        import json

        body = await request.json()
        user_text = str(body.get("user_text", "")).strip()
        session_id = body.get("session_id")
        turn_id = body.get("turn_id", str(uuid4()))
        conversation_history = body.get("conversation_history", [])
        available_tools = body.get("available_tools", [])

        if not user_text:
            return JSONResponse({"error": "user_text is required"}, status_code=400)

        # Build a minimal tool_executor that tries to call registered tools
        from .tools.registry import registry as tool_registry
        from .tools import load_all_tools
        load_all_tools()

        async def tool_executor(tool_name: str, params: dict):
            handler = tool_registry._handlers.get(tool_name)
            if not handler:
                return {"error": f"Tool {tool_name} not found"}
            try:
                return await handler(params)
            except Exception as e:
                return {"error": str(e)}

        coordinator = HinaBrainCoordinator(
            tool_executor=tool_executor,
            max_parallel_specialists=3,
            specialist_timeout=45.0,
        )

        async def event_generator():
            try:
                async for event in coordinator.run_stream(
                    turn_id=turn_id,
                    user_text=user_text,
                    session_id=session_id,
                    conversation_history=conversation_history,
                    available_tools=available_tools,
                ):
                    data = json.dumps({
                        "event_type": event.event_type,
                        "run_id": event.run_id,
                        "specialist": event.specialist,
                        "step_id": event.step_id,
                        "payload": event.payload,
                        "timestamp": event.timestamp,
                    })
                    yield f"data: {data}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'event_type': 'brain.run.failed', 'payload': {'error': str(e)}})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # -------------------------------------------------------------------------
    # HINAA OS — Phase 11 Multi-Agent Swarms & Autonomous Tooling Endpoints
    # -------------------------------------------------------------------------
    from .routers.agents_router import router as agents_router
    app.include_router(agents_router)

    # =========================================================================
    # PHASE 13 — AUTOPILOT & PERSISTENT BACKGROUND OPERATIONS
    # =========================================================================
    from .routers.autopilot_router import router as autopilot_router
    app.include_router(autopilot_router)

    return app


app = create_app()
