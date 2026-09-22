from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
import time
import httpx
from pathlib import Path
from time import perf_counter
from typing import Annotated, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone

from fastapi import Body, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from . import __version__, realtime_tickets
from .audio import validate_wav
from .avatar_assets import AvatarAssetError, AvatarAssetService
from .config import Settings, get_settings
from .errors import HinaaError, hinaa_error_handler, unhandled_error_handler
from .models import ProviderStatus, SpeechRequest, ToolRequest, TranscriptResponse, TurnRequest, VoiceProfile, TextHumanizerRequest, TextHumanizerResponse
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
    fingerprints_for,
    newest_verdict,
)
from .reachability import is_ephemeral_tunnel, probe_gateway, probe_gateway_models
from .realtime import RealtimeGateway
from .services import ConversationService
from .tools import policy as tool_policy, registry
from .vmc_bridge import vmc_bridge
from .voice_profiles import public_profiles
from .artifacts import ArtifactFormat, ArtifactService


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


class ProjectCreateBody(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=180)]
    description: Annotated[str, Field(max_length=4000)] = ""


class ProjectPlanBody(BaseModel):
    goal: Annotated[str, Field(min_length=3, max_length=1000)]


class ProjectTaskBody(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=240)]
    detail: Annotated[str, Field(max_length=8000)] = ""
    parentTaskId: str | None = None
    requiresApproval: bool = False


class ProjectTaskStatusBody(BaseModel):
    status: Annotated[str, Field(pattern="^(pending|active|success|error|cancelled|waiting_approval)$")]


class ProjectAgentRunBody(BaseModel):
    goal: Annotated[str, Field(min_length=3, max_length=4000)]
    rootTaskId: str | None = None


class DocumentPdfBody(BaseModel):
    title: Annotated[str, Field(default="HINAA Report", max_length=240)]
    markdown: Annotated[str, Field(min_length=1, max_length=120_000)]
    subtitle: Annotated[str, Field(max_length=240)] | None = None


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
    text: Annotated[str, Field(min_length=1, max_length=4000)]
    projectState: dict[str, Any] | None = None


class CreateTaskBody(BaseModel):
    goal: Annotated[str, Field(min_length=3, max_length=4000)]
    conversationId: str | None = None
    projectId: str | None = None
    taskType: str = "general"
    priority: int = 0
    reasoningMode: str = "balanced"
    steps: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] | None = None


class ResolveTaskBody(BaseModel):
    text: Annotated[str, Field(min_length=1, max_length=4000)]
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
    reason: Annotated[str, Field(min_length=1, max_length=1000)]
    retryLimit: int = 2


class SteerTaskBody(BaseModel):
    instruction: Annotated[str, Field(min_length=1, max_length=4000)]


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
        "agent-router",
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
        "qwen",
    }
)


def create_app(settings: Settings | None = None) -> FastAPI:
    # Without this, INFO-level breadcrumbs (realtime message trace) and even
    # uncaught-exception logging were effectively invisible: Python's root
    # logger has no handler by default, and the previous bare `except
    # Exception:` in the realtime turn loop did not log at all. This is why
    # turn failures looked like an unexplained "connection lost" with zero
    # server-side trace to diagnose from.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    active_settings = settings or get_settings()
    reset_session_factory()
    session_factory = init_db(active_settings) if active_settings.persistence_enabled else None
    memory_service = (
        MemoryService(session_factory) if session_factory is not None else None
    )
    task_service = (
        TaskService(session_factory) if session_factory is not None else None
    )
    service = ConversationService(active_settings, memory_service=memory_service, task_service=task_service, session_factory=session_factory)
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
        Path(__file__).resolve().parents[3],
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
            tool_def = registry.get_tool(step.tool_name)
            if not tool_def:
                raise HinaaError("TOOL_UNAVAILABLE", f"Tool {step.tool_name} not found", 404)
            handler = registry._handlers.get(step.tool_name)
            if not handler:
                raise HinaaError("TOOL_UNAVAILABLE", f"Tool handler for {step.tool_name} not found", 404)
            tool_policy.enforce(step.tool_name, active_settings)
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
        yield
        tasks = [*project_tasks.values(), *tool_tasks]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        vmc_bridge.stop()

    app = FastAPI(
        title="HINAA API",
        version=__version__,
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = active_settings
    app.state.service = service
    app.state.memory_service = memory_service
    app.state.workspace_service = workspace_service
    app.state.avatar_assets = avatar_assets
    app.state.creative_budget = creative_budget
    app.state.creative_jobs = creative_jobs
    app.state.asset_store = asset_store
    app.state.agent_runtime = agent_runtime
    app.state.task_service = task_service
    app.state.durable_task_bridge = durable_task_bridge
    app.add_middleware(
        CORSMiddleware,
        allow_origins=active_settings.allowed_origins,
        allow_origin_regex=r"https://.*\.vercel\.app",
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Correlation-ID", "X-HINAA-Provider", "X-HINAA-Latency-Ms"],
    )
    app.add_exception_handler(HinaaError, hinaa_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_error_handler)

    @app.middleware("http")
    async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        correlation_id = _correlation_id(request.headers.get("X-Correlation-ID"))
        request.state.correlation_id = correlation_id
        host_token = tool_policy.set_request_host(request.headers.get("host"))
        try:
            response = await call_next(request)
        finally:
            tool_policy.reset_request_host(host_token)
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/health/live")
    async def liveness() -> dict[str, str]:
        return {"status": "ok", "service": "hinaa-api", "version": __version__}

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

    @app.post("/v1/creative/jobs", status_code=201)
    async def create_creative_job(body: CreativeJobBody) -> dict[str, Any]:
        model = CreativeModelRegistry.get_model(body.model)
        job = await creative_jobs.create_job(body.prompt, model.id, model.cost_credits)
        return job.to_dict()

    @app.get("/v1/local-services/comfyui")
    async def comfyui_status() -> JSONResponse:
        from hinaa_api.tools.image_generate import comfyui_provider

        available = await comfyui_provider.health_check()
        return JSONResponse(
            status_code=200 if available else 503,
            content={
                "status": "ready" if available else "unavailable",
                "service": "ComfyUI",
                "localOnly": True,
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
        await vmc_bridge.add_client(ws)
        try:
            while True:
                # Keep connection alive; bridge pushes data on UDP receipt
                await ws.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            vmc_bridge.remove_client(ws)

    @app.get("/health")
    async def health_alias() -> JSONResponse:
        return await readiness()

    @app.get("/health/ready")
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
        ready = not missing
        return JSONResponse(
            status_code=200 if ready else 503,
            content={
                "status": "ok" if ready else "degraded",
                "mode": active_settings.provider_mode,
                "missingConfiguration": missing if not ready else [],
                "persistenceEnabled": active_settings.persistence_enabled,
                "authMode": active_settings.auth_mode,
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
                "defaultModel": "gemini-2.5-pro",
                "allowedModels": ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-1.5-pro"],
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
            if provider_id in {"you", "omniroute"}:
                continue  # research lane and last-resort gateway, not pickable brains
            if not provider.get("configured"):
                # An unconfigured brain cannot answer; listing it would be the
                # same "fake model list" defect the audit flagged.
                continue
            for model_id in provider.get("allowedModels") or []:
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
                "webSearch": has_ydc,
                "artifacts": bool(active_settings.persistence_enabled),
                "goals": bool(active_settings.agent_runtime_enabled),
                # Named for what it measures: the serial agent runtime gate. There
                # is no parallel worker cluster yet, so none is reported.
                "agentRuntime": bool(active_settings.agent_runtime_enabled),
                "memory": bool(active_settings.persistence_enabled),
                "speech": has_elevenlabs or has_azure,
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
        is_loopback = "127.0.0.1" in base or "localhost" in base or "0.0.0.0" in base
        if active_settings.ollama_configured:
            if is_server_remote and is_loopback:
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
                    "llm",
                    "s2s",
                    "native-bidi-audio",
                    "pcm-24khz",
                    "barge-in-native",
                    "default-model:gemini-2.5-flash",
                ],
                state="healthy" if active_settings.gemini_configured else "unavailable",
                userMessage=(
                    "Gemini Live Bidi S2S (sub-300ms native multimodal audio) is ready."
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
            measured = newest_verdict(
                aliases_for(status.id),
                fingerprints=fingerprints_for(active_settings, status.id),
            )
            if measured is not None:
                status.state = measured.state
                status.userMessage = measured.message
            elif status.state == "healthy" and status.id not in probe_measured:
                status.state = "untested"
                if "no live call" not in status.userMessage.lower():
                    status.userMessage = (
                        f"{status.userMessage} No live call has been made yet."
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
                )
            )
        ) or bool(os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("DEEPSEEK_PKAY_API_KEY"))
        has_speech = any(
            bool(getattr(active_settings, f"{name}_configured", False))
            for name in ("elevenlabs", "azure", "fish_audio", "deepgram")
        )
        persistence_on = bool(active_settings.persistence_enabled)
        runtime_on = bool(active_settings.agent_runtime_enabled)

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
    async def realtime_ticket(request: Request) -> dict[str, object]:
        """Buy the identity a WebSocket handshake cannot carry.

        A browser cannot set an Authorization header when it opens a socket, so
        the voice route would otherwise never learn who it is talking to and
        would answer with no memory of him. He asks here instead, over a request
        that does prove who he is, and spends the result in the socket's first
        frame. The ticket is short lived and single use, and it never rides in a
        URL where a proxy or an access log could keep it.
        """
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
            "ticket": realtime_tickets.issue(auth.user_id),
            "expiresInSeconds": realtime_tickets.TICKET_TTL_SECONDS,
        }

    @app.websocket("/v1/realtime")
    async def realtime_session(websocket: WebSocket) -> None:
        await realtime.handle(websocket, user_id=_resolve_user_id(websocket))

    @app.get("/v1/realtime/url")
    async def realtime_url(request: Request) -> dict[str, object]:
        """Where a browser must open the realtime WebSocket.

        The deployed frontend cannot use its own origin: Vercel rewrites proxy
        HTTP but not WebSocket upgrades, so wss://<vercel-host>/…/realtime can
        never reach this process. The tunnel hostname also changes every time a
        quick tunnel restarts, so the answer is derived per request rather than
        baked into the bundle.
        """
        configured = (active_settings.realtime_public_origin or "").strip()
        host = (request.headers.get("host") or "").strip()
        forwarded_host = (request.headers.get("x-forwarded-host") or "").strip()

        origin = (configured or host).lower()
        for prefix in ("https://", "http://", "wss://", "ws://"):
            if origin.startswith(prefix):
                origin = origin[len(prefix) :]
                break
        origin = origin.rstrip("/")

        is_local = origin.split(":")[0] in {"localhost", "127.0.0.1", "[::1]"}
        forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip()
        tls = forwarded_proto == "https" if forwarded_proto else not is_local
        return {
            "url": f"{'wss' if tls else 'ws'}://{origin}/v1/realtime" if origin else None,
            "source": "configured" if configured else ("host" if host else "unavailable"),
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
        settings = _studio_settings()
        cloud_ready = bool(getattr(settings, "magnific_configured", False))
        comfy_ready = False
        try:
            from hinaa_api.tools.image_generate import comfyui_provider
            comfy_ready = bool(await comfyui_provider.health_check())
        except Exception:  # noqa: BLE001 - diagnostics must never 500
            comfy_ready = False
        if cloud_ready:
            renderer, detail = "magnific-flux", "Magnific FLUX cloud generation is active."
        elif comfy_ready:
            renderer, detail = "comfyui-local", "Cloud key not found — generating through local ComfyUI."
        else:
            renderer, detail = "none", "No image renderer is reachable right now."
        return {
            "renderer": renderer,
            "magnificConfigured": cloud_ready,
            "comfyAvailable": comfy_ready,
            "detail": detail,
            "setup": [] if cloud_ready else [
                "Add MAGNIFIC_API_KEY=<your Freepik/Magnific developer key> to apps/api/.env.local",
                "Get a key at https://www.freepik.com/developers/dashboard/api-key",
                "Or start ComfyUI on http://127.0.0.1:8188 for fully local generation",
                "Restart the API afterwards (uvicorn reads .env.local at boot)",
            ],
        }

    @app.get("/v1/generated-images")
    async def list_generated_images(limit: int = 50) -> dict[str, object]:
        """Every image file HINAA actually produced, newest first.

        The Library view fetches /api/v1/generated-images, which had no route
        and so fell through to fabricated demo rows. Declared under /v1 so the
        generic alias block below also serves the /api/v1 form.
        """
        from datetime import datetime, timezone
        from pathlib import Path

        from hinaa_api.config import DATA_DIR

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

        entries: list[dict[str, object]] = []
        images_root = DATA_DIR / "images"
        if images_root.exists():
            suffixes = {".png", ".jpg", ".jpeg", ".webp"}
            files = [
                path
                for path in images_root.iterdir()
                if path.is_file() and path.suffix.lower() in suffixes
            ]
            files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
            for path in files[:page]:
                stat = path.stat()
                entries.append(
                    {
                        "id": path.name,
                        "filename": path.name,
                        "url": f"/api/v1/generated-images/{path.name}",
                        "prompt": prompts.get(path.stem) or prompts.get(path.name),
                        "created_at": datetime.fromtimestamp(
                            stat.st_mtime, tz=timezone.utc
                        ).isoformat(),
                        "sizeKb": round(stat.st_size / 1024, 1),
                    }
                )
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
    async def get_generated_document(doc_id: str):
        from fastapi.responses import FileResponse
        from pathlib import Path

        allowed_roots = [
            (Path(__file__).resolve().parent / "data" / "documents").resolve(),
            (Path(__file__).resolve().parent.parent / "data" / "documents").resolve(),
            Path("apps/api/data/documents").resolve(),
            Path("apps/api/hinaa_api/data/documents").resolve(),
        ]

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

        return FileResponse(
            resolved_path,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{resolved_path.name}"'},
        )


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
        tool_def = registry.get_tool(body.toolName)
        if not tool_def:
            raise HTTPException(status_code=404, detail="Tool not found")
        verdict = tool_policy.decide(body.toolName, active_settings, request.headers.get("host"))
        if not verdict.permitted:
            raise HinaaError(verdict.code, verdict.message, 403, False, True)
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
            )
        )
        if tool_def.requires_confirmation and not (is_user_approved or is_safe_standing_consent):
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
            
            # Server-resolved owner identity overrides client payload
            server_user_id = _resolve_user_id(request)
            parsed_params.pop("userId", None)
            parsed_params.pop("user_id", None)
            if server_user_id:
                parsed_params["userId"] = server_user_id

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
    async def lookup_artifact(
        request: Request,
        kind: str,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Look up an artifact by kind (pdf, docx, pptx, image, etc.) in the current session or recent tasks."""
        # Local workspace artifacts are scoped to the configured development
        # owner and do not require persistent auth. Persistent artifacts still
        # require server-resolved identity below.
        if memory_service is None:
            local_artifact = workspace_service.latest_artifact(_workspace_user_id(request), kind)
            if not local_artifact:
                return {"found": False, "kind": kind}
            return {
                "found": True,
                "artifact": local_artifact,
                "downloadUrl": f"/v1/projects/artifacts/{local_artifact['id']}/export",
            }

        user_id = _resolve_user_id(request)
        if not user_id:
            raise HinaaError("AUTH_REQUIRED", "Authentication required for artifact lookup", 401, True)
        
        # Search in project artifacts for the current user
        from .persistence.db import get_session_factory
        from .persistence.orm import ProjectArtifact
        from .config import get_settings
        
        session_factory = get_session_factory(active_settings)
        
        with session_factory() as session:
            query = session.query(ProjectArtifact).filter(
                ProjectArtifact.user_id == user_id,
                ProjectArtifact.kind == kind,
            )
            if session_id:
                # Filter by conversation/session if provided
                pass  # Would need conversation linkage
            
            # Get the most recent artifact of this kind
            artifact = query.order_by(ProjectArtifact.created_at.desc()).first()
            
            if not artifact:
                return {
                    "found": False,
                    "kind": kind,
                    "message": f"No {kind.upper()} artifact found in your projects.",
                    "suggestion": f"Use /{kind} to create a new {kind.upper()} document.",
                }
            
            return {
                "found": True,
                "artifact": {
                    "id": artifact.id,
                    "kind": artifact.kind,
                    "title": artifact.title,
                    "createdAt": artifact.created_at.isoformat() if artifact.created_at else None,
                    "projectId": artifact.project_id,
                    "metadata": artifact.metadata,
                },
                "downloadUrl": f"/api/v1/projects/artifacts/{artifact.id}/export",
            }

    # -----------------------------------------------------------------------
    # Phase 14: Artifact OS REST Surface
    # -----------------------------------------------------------------------

    @app.post("/v1/artifacts/documents", status_code=201)
    async def create_document_artifact(
        request: Request, body: CreateDocumentArtifactBody
    ) -> dict[str, Any]:
        user_id = _workspace_user_id(request)
        try:
            fmt = ArtifactFormat(body.format.lower())
        except ValueError:
            fmt = ArtifactFormat.MD
        record, doc_ast = artifact_service.create_document(
            user_id=user_id,
            title=body.title,
            content=body.content,
            project_id=body.projectId,
            conversation_id=body.conversationId,
            task_id=body.taskId,
            format=fmt,
            tags=body.tags,
        )
        inspection = artifact_service.inspector.inspect_document(doc_ast)
        return {
            "artifact": record.model_dump(mode="json"),
            "inspection": {
                "wordCount": inspection.word_count,
                "readingTimeMinutes": inspection.reading_time_minutes,
                "estimatedTokens": inspection.estimated_tokens,
                "qualityScore": inspection.quality_score,
                "passed": inspection.passed,
                "tocEntries": [
                    {"level": e.level, "title": e.title, "anchorId": e.anchor_id}
                    for e in inspection.table_of_contents
                ],
            },
            "downloadUrl": f"/v1/artifacts/{record.id}/export",
        }

    @app.post("/v1/artifacts/presentations", status_code=201)
    async def create_presentation_artifact(
        request: Request, body: CreatePresentationArtifactBody
    ) -> dict[str, Any]:
        user_id = _workspace_user_id(request)
        record, _ = artifact_service.create_presentation(
            user_id=user_id,
            title=body.title,
            slides_data=body.slides,
            subtitle=body.subtitle,
            project_id=body.projectId,
            conversation_id=body.conversationId,
            task_id=body.taskId,
        )
        return {
            "artifact": record.model_dump(mode="json"),
            "downloadUrl": f"/v1/artifacts/{record.id}/export?format=pptx",
        }

    @app.post("/v1/artifacts/spreadsheets", status_code=201)
    async def create_spreadsheet_artifact(
        request: Request, body: CreateSpreadsheetArtifactBody
    ) -> dict[str, Any]:
        user_id = _workspace_user_id(request)
        record, _ = artifact_service.create_spreadsheet(
            user_id=user_id,
            title=body.title,
            sheets_data=body.sheets,
            project_id=body.projectId,
            conversation_id=body.conversationId,
            task_id=body.taskId,
        )
        return {
            "artifact": record.model_dump(mode="json"),
            "downloadUrl": f"/v1/artifacts/{record.id}/export?format=xlsx",
        }

    @app.get("/v1/artifacts/{artifact_id}")
    async def get_artifact_endpoint(artifact_id: str) -> dict[str, Any]:
        art = artifact_service.get_artifact(artifact_id)
        if not art:
            raise HTTPException(status_code=404, detail="Artifact not found")
        return {"artifact": art.model_dump(mode="json")}

    @app.get("/v1/artifacts/{artifact_id}/inspect")
    async def inspect_artifact_endpoint(artifact_id: str) -> dict[str, Any]:
        try:
            report = artifact_service.inspect_artifact(artifact_id)
            return {"report": report}
        except KeyError:
            raise HTTPException(status_code=404, detail="Artifact not found")

    @app.get("/v1/artifacts/{artifact_id}/export")
    async def export_artifact_endpoint(artifact_id: str, format: str | None = None) -> Response:
        art = artifact_service.get_artifact(artifact_id)
        if not art:
            raise HTTPException(status_code=404, detail="Artifact not found")

        target_fmt_str = format or art.format.value
        try:
            target_fmt = ArtifactFormat(target_fmt_str.lower())
        except ValueError:
            target_fmt = art.format

        try:
            exported = artifact_service.export_artifact(artifact_id, target_fmt)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Export failed: {exc}") from exc

        from .artifacts.models import MIME_TYPE_MAP
        media_type = MIME_TYPE_MAP.get(target_fmt, "application/octet-stream")
        filename = f"{art.title.lower().replace(' ', '_')[:40]}.{target_fmt.value}"
        content_bytes = exported if isinstance(exported, bytes) else exported.encode("utf-8")

        return Response(
            content=content_bytes,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-store",
            },
        )

    @app.post("/v1/artifacts/package")
    async def package_artifacts_endpoint(body: PackageArtifactsBody) -> Response:
        zip_bytes = artifact_service.package_artifacts(
            body.artifactIds, body.bundleTitle, body.description
        )
        filename = f"{body.bundleTitle.lower().replace(' ', '_')[:40]}_package.zip"
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-store",
            },
        )

    @app.get("/v1/conversations")
    @app.get("/api/v1/conversations")
    async def list_conversations(
        auth: AuthContext | None = Depends(conversation_auth),
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        if memory_service is None or auth is None:
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
        if memory_service is None or auth is None:
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
        # The dev subject is a local-only owner. Filing an unidentified public
        # turn under it put strangers' runs in the same bucket as his own.
        owner_id = user_id or (
            active_settings.dev_auth_subject if not reached_through_edge(request) else None
        )
        if active_settings.agent_runtime_enabled and agent_runtime is not None and owner_id:
            agent_run = agent_runtime.create_run(
                goal=body.text,
                user_id=owner_id,
                conversation_id=body.conversationId or body.sessionId,
            )

        async def guarded_stream():  # type: ignore[no-untyped-def]
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
                    body, request.state.correlation_id, user_id=user_id
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
                        if decoded.get("type") == "plan" and isinstance(decoded.get("plan"), dict):
                            final_plan_payload = decoded["plan"]
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

        return StreamingResponse(guarded_stream(), media_type="application/x-ndjson")

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

    @app.post("/v1/speech/synthesis")
    @app.post("/api/v1/speech/synthesis")
    async def synthesize(body: SpeechRequest) -> Response:
        started = perf_counter()
        result = await service.synthesize(body)
        media_type = "audio/mpeg" if result.provider == "elevenlabs" else "audio/wav"
        return Response(
            result.value,
            media_type=media_type,
            headers={
                "X-HINAA-Provider": result.provider,
                "X-HINAA-Latency-Ms": str(result.latency_ms),
                "X-HINAA-Total-Ms": str(int((perf_counter() - started) * 1000)),
                "Content-Disposition": 'inline; filename="hinaa-turn.wav"',
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

    @app.get("/v1/generated-docs")
    @app.get("/api/v1/generated-docs")
    async def list_generated_documents() -> dict[str, object]:
        """List HINAA-generated documents (metadata files on disk), newest first."""
        import json as _json
        from datetime import datetime, timezone
        from pathlib import Path

        roots = [
            (Path(__file__).resolve().parent / "data" / "documents").resolve(),
            (Path(__file__).resolve().parent.parent / "data" / "documents").resolve(),
            Path("apps/api/data/documents").resolve(),
            Path("apps/api/hinaa_api/data/documents").resolve(),
        ]
        docs: list[dict[str, object]] = []
        seen: set[str] = set()
        for root in roots:
            if not root.exists():
                continue
            metas = sorted(root.glob("*.metadata.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            for meta_path in metas:
                try:
                    meta = _json.loads(meta_path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if not isinstance(meta, dict):
                    continue
                doc_id = str(meta.get("docId") or meta_path.name.removesuffix(".metadata.json"))
                if doc_id in seen:
                    continue
                seen.add(doc_id)
                docs.append(
                    {
                        "docId": doc_id,
                        "title": meta.get("title") or meta.get("filename") or doc_id,
                        "filename": meta.get("filename"),
                        "format": meta.get("format") or "pdf",
                        "pageCount": meta.get("pageCount"),
                        "fileSizeKb": meta.get("fileSizeKb"),
                        "topic": meta.get("topic"),
                        "downloadUrl": meta.get("downloadUrl") or f"/api/v1/generated-docs/{doc_id}",
                        "createdAt": datetime.fromtimestamp(meta_path.stat().st_mtime, tz=timezone.utc).isoformat(),
                    }
                )
        return {"documents": docs, "count": len(docs)}

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

    return app


app = create_app()
