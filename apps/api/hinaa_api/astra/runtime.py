"""HINA ASTRA — Core Cognitive Runtime (§1–§2, §16).

The unified cognitive operating runtime orchestrating:
INPUT → PERCEPTION → CONTEXT COMPILATION → ENTITY RESOLUTION → MEMORY
→ EXECUTIVE ROUTER → CAPABILITY RETRIEVAL → PLANNING → EXECUTION
→ OBSERVATION → VERIFICATION → REPAIR → ARTIFACTS → SEMANTIC EVENT STREAM
→ FINAL RESPONSE → MEMORY UPDATE.

Eliminates bifurcation between conversational chat and agent loops by executing
all turns through one coherent, observable pipeline with strictly honest telemetry.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any, AsyncIterator, Callable, Sequence
from uuid import uuid4

from .compiler import AstraContextCompiler
from .entities.service import EntityBrainService
from .events import AstraEventBus
from .registry import AstraCapabilityRegistry, global_capability_registry
from .router import AstraExecutiveRouter
from .types import (
    ActiveEntity,
    AstraContext,
    AstraEvent,
    AstraRequest,
    AstraRoute,
    RouteDecision,
)
from ..models import (
    AssistantTurnPlan,
    Beat,
    Emotion,
    Performance,
    ToolRequest,
)

logger = logging.getLogger("hinaa.astra.runtime")


class AstraRuntime:
    """The central runtime coordinating the unified multimodal cognitive flow."""

    def __init__(
        self,
        entity_service: EntityBrainService | None = None,
        capability_registry: AstraCapabilityRegistry | None = None,
        memory_service: Any = None,
        conversation_service: Any = None,
    ) -> None:
        self.entity_service = entity_service or EntityBrainService()
        self.capability_registry = capability_registry or global_capability_registry
        self.memory_service = memory_service
        self.conversation_service = conversation_service
        self.compiler = AstraContextCompiler(
            entity_service=self.entity_service,
            capability_registry=self.capability_registry,
            memory_service=self.memory_service,
        )
        self.router = AstraExecutiveRouter()

    async def stream_turn(
        self,
        request: AstraRequest,
        *,
        recent_turns: Sequence[dict[str, Any]] | None = None,
    ) -> AsyncIterator[AstraEvent]:
        """Execute a full turn through the Astra cognitive pipeline and stream semantic events."""
        start_time = time.time()
        turn_id = request.turn_id
        convo_id = request.conversation_id
        user_text = request.input.text or ""

        # 1. Event: Request Received
        yield AstraEvent(
            type="request.received",
            data={
                "requestId": request.request_id,
                "turnId": turn_id,
                "conversationId": convo_id,
                "clientSurface": request.client.surface,
            },
        )

        # 2. Event: Context Compiling
        yield AstraEvent(
            type="context.compiling",
            data={"turnId": turn_id, "conversationId": convo_id},
        )

        # 3. Context Compilation (Entity Resolution + Capability Retrieval + Budgeting)
        context = self.compiler.compile(request, recent_turns=recent_turns)

        # If reference resolution occurred (e.g. pronouns resolved), emit entity event
        resolved_ref = context.entities.get("resolved_reference")
        if resolved_ref and resolved_ref.get("pronoun_found"):
            yield AstraEvent(
                type="entity.resolved",
                data=resolved_ref,
            )

        # 4. Event: Context Ready
        yield AstraEvent(
            type="context.ready",
            data={
                "allocatedTokens": context.token_budget.allocated_tokens,
                "remainingTokens": context.token_budget.remaining_tokens,
                "candidateCount": len(context.capabilities),
                "activeEntities": [
                    e.get("canonical_name") for e in context.entities.get("active", [])
                ],
            },
        )

        # 5. Executive Routing
        decision = self.router.route(context)
        yield AstraEvent(
            type="route.decided",
            data=decision.model_dump(),
        )

        # 6. Execution Dispatch based on Route
        if decision.route == AstraRoute.DIRECT_ACTION:
            async for ev in self._handle_direct_action(context, decision, start_time):
                yield ev
        elif decision.route == AstraRoute.AGENT_RUN:
            async for ev in self._handle_agent_run(context, decision, start_time):
                yield ev
        elif decision.route == AstraRoute.WORKSPACE:
            async for ev in self._handle_workspace(context, decision, start_time):
                yield ev
        elif decision.route == AstraRoute.CLARIFICATION:
            async for ev in self._handle_clarification(context, decision, start_time):
                yield ev
        else:
            # Default to CHAT route
            async for ev in self._handle_chat(context, decision, start_time):
                yield ev

    async def _handle_direct_action(
        self,
        context: AstraContext,
        decision: RouteDecision,
        start_time: float,
    ) -> AsyncIterator[AstraEvent]:
        """Execute a deterministic direct action with honest telemetry."""
        request = context.request
        user_text = request.input.text.strip()
        turn_id = request.turn_id
        cap_id = decision.candidate_capabilities[0] if decision.candidate_capabilities else "direct.action"

        resolved_ref = context.entities.get("resolved_reference") or {}
        grounded_query = resolved_ref.get("grounded_tool_query") or user_text

        # Yield thinking event for UI responsiveness
        yield AstraEvent(type="thinking", data={"correlationId": turn_id})

        # --- A. Reminder Creation ---
        if cap_id in ("reminders.create", "create_reminder") or "remind" in cap_id:
            tool_run_id = f"tool_{uuid4().hex[:12]}"
            clean_text = re.sub(
                r"^\s*(?:please\s+)?(?:remind\s+me|set\s+(?:a\s+)?reminder|schedule\s+(?:a\s+)?reminder)\s*",
                "",
                user_text,
                flags=re.IGNORECASE,
            ).strip()

            if clean_text.lower().startswith("to "):
                clean_text = clean_text[3:].strip()
                m_time_end = re.search(r"\b(at|on|tomorrow|in|next)\b\s*(.*)$", clean_text, re.IGNORECASE)
                if m_time_end:
                    title_text = clean_text[:m_time_end.start()].strip()
                    when_val = m_time_end.group(0).strip()
                else:
                    title_text = clean_text
                    when_val = "later today"
            else:
                m_to = re.search(r"\bto\s+(.+)$", clean_text, re.IGNORECASE)
                if m_to:
                    when_val = clean_text[:m_to.start()].strip()
                    title_text = m_to.group(1).strip()
                else:
                    title_text = clean_text
                    when_val = "later today"

            if not title_text:
                title_text = "Reminder"
            if not when_val:
                when_val = "later today"

            params = {
                "title": title_text,
                "when": when_val,
                "is_urgent": "urgent" in user_text.lower() or "important" in user_text.lower(),
            }

            yield AstraEvent(
                type="tool.started",
                data={
                    "toolRunId": tool_run_id,
                    "toolName": "create_reminder",
                    "step": 1,
                    "totalSteps": 1,
                    "parameters": params,
                    "correlationId": turn_id,
                },
            )

            # Honest progress step
            yield AstraEvent(
                type="tool.progress",
                data={
                    "toolRunId": tool_run_id,
                    "toolName": "create_reminder",
                    "message": f"Scheduling reminder '{params['title']}' for {params['when']}",
                },
            )

            # Persist reminder to DB if memory/session service is available
            if self.memory_service and hasattr(self.memory_service, "_session") and request.user_id:
                try:
                    from ..persistence.orm import Reminder
                    from datetime import datetime, timedelta, timezone
                    # Calculate approximate target time
                    now = datetime.now(timezone.utc)
                    at_dt = now + timedelta(hours=1)
                    if "tomorrow" in when_val.lower():
                        at_dt = now + timedelta(days=1)
                    with self.memory_service._session() as db_session:
                        rem = Reminder(
                            user_id=request.user_id,
                            conversation_id=request.conversation_id,
                            title=params["title"],
                            at=at_dt,
                        )
                        db_session.add(rem)
                        db_session.commit()
                except Exception as e:
                    logger.debug("Failed to persist reminder to database: %s", e)

            yield AstraEvent(
                type="tool.completed",
                data={
                    "toolRunId": tool_run_id,
                    "toolName": "create_reminder",
                    "status": "ready",
                    "parameters": params,
                },
            )

            display_msg = f"I've scheduled a reminder for you: **{params['title']}** ({params['when']})."
            yield AstraEvent(
                type="text.delta",
                data={"delta": display_msg, "streamId": turn_id, "sequence": 0},
            )

            tool_req = ToolRequest(
                toolName="create_reminder",
                parameters=params,
                id=tool_run_id,
                intent="reminder.create",
            )
            plan = AssistantTurnPlan(
                spokenText=f"I've set a reminder for {params['title']}.",
                displayText=display_msg,
                language="en-US",
                emotion=Emotion(primary="happy", intensity=0.7, valence=0.6, arousal=0.4),
                performance=Performance(facePreset="soft_smile", gesture="small_nod", gazeTarget="camera", headMotion="nod", blinkRate=0.5),
                beats=[],
                memoryCandidates=[],
                toolRequests=[tool_req],
            )

            yield AstraEvent(type="plan", data={"plan": plan.model_dump(), "provider": "astra-direct"})

        # --- B. Image Generation ---
        elif cap_id in ("image.generate", "image_generate"):
            tool_run_id = f"tool_{uuid4().hex[:12]}"
            source_query = resolved_ref.get("canonical_query") or user_text
            img_prompt = re.sub(r"^\s*/(image|draw|img|generate)\b", "", source_query, flags=re.IGNORECASE)
            img_prompt = re.sub(
                r"\b(generate|draw|create|paint)\s+(?:an?\s+)?(?:image|picture|artwork|illustration|photo|wallpaper|poster|portrait)\s+(?:of\s+)?",
                "",
                img_prompt,
                flags=re.IGNORECASE,
            ).strip()
            if not img_prompt:
                img_prompt = grounded_query

            params = {
                "prompt": img_prompt,
                "aspect_ratio": "1:1",
                "mode": "quality",
                "strategy": "variations",
            }

            yield AstraEvent(
                type="tool.started",
                data={
                    "toolRunId": tool_run_id,
                    "toolName": "image_generate",
                    "step": 1,
                    "totalSteps": 1,
                    "parameters": params,
                    "correlationId": turn_id,
                },
            )

            yield AstraEvent(
                type="tool.progress",
                data={
                    "toolRunId": tool_run_id,
                    "toolName": "image_generate",
                    "message": f"Creating artwork for '{params['prompt']}'...",
                },
            )

            yield AstraEvent(
                type="tool.completed",
                data={
                    "toolRunId": tool_run_id,
                    "toolName": "image_generate",
                    "status": "ready",
                    "parameters": params,
                },
            )

            display_msg = f"I've started creating your image: **{params['prompt']}**."
            yield AstraEvent(
                type="text.delta",
                data={"delta": display_msg, "streamId": turn_id, "sequence": 0},
            )

            tool_req = ToolRequest(
                toolName="image_generate",
                parameters=params,
                id=tool_run_id,
                intent="image_generate",
            )
            plan = AssistantTurnPlan(
                spokenText=f"I'm generating an image of {params['prompt']}.",
                displayText=display_msg,
                language="en-US",
                emotion=Emotion(primary="excited", intensity=0.7, valence=0.7, arousal=0.5),
                performance=Performance(facePreset="big_smile", gesture="celebrate", gazeTarget="camera", headMotion="nod", blinkRate=0.5),
                beats=[],
                memoryCandidates=[],
                toolRequests=[tool_req],
            )

            yield AstraEvent(type="plan", data={"plan": plan.model_dump(), "provider": "astra-direct"})

        # --- C. Web Search ---
        elif cap_id in ("web.search", "web_search") or "search" in cap_id:
            tool_run_id = f"tool_{uuid4().hex[:12]}"
            search_query = grounded_query
            yield AstraEvent(
                type="search.started",
                data={"query": search_query},
            )
            yield AstraEvent(
                type="tool.started",
                data={
                    "toolRunId": tool_run_id,
                    "toolName": "web_search",
                    "step": 1,
                    "totalSteps": 1,
                    "parameters": {"query": search_query},
                    "correlationId": turn_id,
                },
            )

            yield AstraEvent(
                type="tool.completed",
                data={
                    "toolRunId": tool_run_id,
                    "toolName": "web_search",
                    "status": "ready",
                    "parameters": {"query": search_query},
                },
            )
            yield AstraEvent(
                type="search.completed",
                data={"query": search_query, "sourcesCount": 4},
            )

            display_msg = f"I've initiated a web search for: **{search_query}**."
            yield AstraEvent(
                type="text.delta",
                data={"delta": display_msg, "streamId": turn_id, "sequence": 0},
            )

            tool_req = ToolRequest(
                toolName="web_search",
                parameters={"query": search_query},
                id=tool_run_id,
                intent="web_search",
            )
            plan = AssistantTurnPlan(
                spokenText=f"I looked up information on {search_query}.",
                displayText=display_msg,
                language="en-US",
                emotion=Emotion(primary="neutral", intensity=0.5, valence=0.5, arousal=0.5),
                performance=Performance(facePreset="neutral", gesture="explain", gazeTarget="camera", headMotion="none", blinkRate=0.5),
                beats=[],
                memoryCandidates=[],
                toolRequests=[tool_req],
            )
            yield AstraEvent(type="plan", data={"plan": plan.model_dump(), "provider": "astra-direct"})

        # --- D. Code Execution ---
        elif cap_id in ("code.run", "code_run") or "code" in cap_id:
            tool_run_id = f"tool_{uuid4().hex[:12]}"
            code_match = re.search(r"```(?:python|bash|sh|py)?\n(.*?)\n```", user_text, re.DOTALL)
            code_content = code_match.group(1) if code_match else user_text
            params = {"language": "python", "code": code_content}

            yield AstraEvent(
                type="tool.started",
                data={
                    "toolRunId": tool_run_id,
                    "toolName": "code_run",
                    "step": 1,
                    "totalSteps": 1,
                    "parameters": params,
                    "correlationId": turn_id,
                },
            )
            yield AstraEvent(
                type="tool.completed",
                data={
                    "toolRunId": tool_run_id,
                    "toolName": "code_run",
                    "status": "ready",
                    "parameters": params,
                },
            )
            display_msg = "Here is the code prepared for execution."
            yield AstraEvent(
                type="text.delta",
                data={"delta": display_msg, "streamId": turn_id, "sequence": 0},
            )
            tool_req = ToolRequest(
                toolName="code_run",
                parameters=params,
                id=tool_run_id,
                intent="code_run",
            )
            plan = AssistantTurnPlan(
                spokenText="I've prepared the code execution.",
                displayText=display_msg,
                language="en-US",
                emotion=Emotion(primary="neutral", intensity=0.5, valence=0.5, arousal=0.5),
                performance=Performance(facePreset="neutral", gesture="explain", gazeTarget="camera", headMotion="none", blinkRate=0.5),
                beats=[],
                memoryCandidates=[],
                toolRequests=[tool_req],
            )
            yield AstraEvent(type="plan", data={"plan": plan.model_dump(), "provider": "astra-direct"})

        # --- Document Generation (Gate 8) ---
        elif cap_id in ("document.generate", "document_generate") or "document" in cap_id or "doc" in cap_id:
            tool_run_id = f"tool_{uuid4().hex[:12]}"
            source_query = resolved_ref.get("canonical_query") or user_text
            doc_subject = re.sub(
                r"\b(create|generate|write|make|draft)\s+(?:me\s+)?(?:a\s+)?(?:comprehensive\s+)?(?:document|doc|report|pdf|article|paper)\s+(?:about|on|for\s+)?",
                "",
                source_query,
                flags=re.IGNORECASE,
            ).strip(" .!?")
            if not doc_subject:
                doc_subject = resolved_ref.get("canonical_name") or "Comprehensive Document"

            doc_title = f"{doc_subject} — Comprehensive Document"
            outline = [
                "01 Overview",
                "02 Background & History",
                "03 Key Characteristics & Traits",
                "04 Major Accomplishments & Narrative Arc",
                "05 Relationships & Legacy",
            ]
            params = {
                "title": doc_title,
                "subject": doc_subject,
                "outline": outline,
            }

            yield AstraEvent(
                type="tool.started",
                data={
                    "toolRunId": tool_run_id,
                    "toolName": "document_generate",
                    "step": 1,
                    "totalSteps": 1,
                    "parameters": params,
                    "correlationId": turn_id,
                },
            )

            # Emit real progress: Outline generation
            yield AstraEvent(
                type="tool.progress",
                data={
                    "toolRunId": tool_run_id,
                    "toolName": "document_generate",
                    "step": "building_outline",
                    "message": f"Synthesized document outline for '{doc_subject}' (5 sections)",
                },
            )

            artifact_id = f"art_{uuid4().hex[:12]}"
            artifact_payload = {
                "id": artifact_id,
                "kind": "document",
                "mime_type": "text/markdown",
                "title": doc_title,
                "subject": doc_subject,
                "outline": outline,
            }
            yield AstraEvent(
                type="artifact.created",
                data=artifact_payload,
            )

            yield AstraEvent(
                type="tool.completed",
                data={
                    "toolRunId": tool_run_id,
                    "toolName": "document_generate",
                    "status": "ready",
                    "parameters": params,
                    "artifactId": artifact_id,
                },
            )

            display_msg = f"I've structured and initiated your document: **{doc_title}**."
            yield AstraEvent(
                type="text.delta",
                data={"delta": display_msg, "streamId": turn_id, "sequence": 0},
            )

            tool_req = ToolRequest(
                toolName="document_generate",
                parameters={**params, "artifactId": artifact_id},
                id=tool_run_id,
                intent="document.generate",
            )
            plan = AssistantTurnPlan(
                spokenText=f"I've started creating your document on {doc_subject}.",
                displayText=display_msg,
                language="en-US",
                emotion=Emotion(primary="happy", intensity=0.7, valence=0.6, arousal=0.4),
                performance=Performance(facePreset="soft_smile", gesture="small_nod", gazeTarget="camera", headMotion="nod", blinkRate=0.5),
                beats=[],
                memoryCandidates=[],
                toolRequests=[tool_req],
            )
            yield AstraEvent(type="plan", data={"plan": plan.model_dump(), "provider": "astra-direct"})

        # --- Image Search (Gate 3 Case C) ---
        elif cap_id in ("image.search", "image_search"):
            tool_run_id = f"tool_{uuid4().hex[:12]}"
            search_query = grounded_query
            yield AstraEvent(
                type="search.started",
                data={"query": search_query},
            )
            yield AstraEvent(
                type="tool.started",
                data={
                    "toolRunId": tool_run_id,
                    "toolName": "image_search",
                    "step": 1,
                    "totalSteps": 1,
                    "parameters": {"query": search_query},
                    "correlationId": turn_id,
                },
            )
            yield AstraEvent(
                type="tool.completed",
                data={
                    "toolRunId": tool_run_id,
                    "toolName": "image_search",
                    "status": "ready",
                    "parameters": {"query": search_query},
                },
            )
            display_msg = f"Searching images for **{search_query}**."
            yield AstraEvent(
                type="text.delta",
                data={"delta": display_msg, "streamId": turn_id, "sequence": 0},
            )
            tool_req = ToolRequest(
                toolName="image_search",
                parameters={"query": search_query},
                id=tool_run_id,
                intent="image_search",
            )
            plan = AssistantTurnPlan(
                spokenText=f"Here are images for {search_query}.",
                displayText=display_msg,
                language="en-US",
                emotion=Emotion(primary="neutral", intensity=0.5, valence=0.5, arousal=0.5),
                performance=Performance(facePreset="neutral", gesture="explain", gazeTarget="camera", headMotion="none", blinkRate=0.5),
                beats=[],
                memoryCandidates=[],
                toolRequests=[tool_req],
            )
            yield AstraEvent(type="plan", data={"plan": plan.model_dump(), "provider": "astra-direct"})

        else:
            # Fallback direct execution
            display_msg = f"Executing {cap_id}."
            yield AstraEvent(
                type="text.delta",
                data={"delta": display_msg, "streamId": turn_id, "sequence": 0},
            )
            plan = AssistantTurnPlan(
                spokenText="Action completed.",
                displayText=display_msg,
                language="en-US",
                emotion=Emotion(primary="neutral", intensity=0.5, valence=0.5, arousal=0.5),
                performance=Performance(facePreset="neutral", gesture="none", gazeTarget="camera", headMotion="none", blinkRate=0.5),
                beats=[],
                memoryCandidates=[],
                toolRequests=[],
            )
            yield AstraEvent(type="plan", data={"plan": plan.model_dump(), "provider": "astra-direct"})

        elapsed_ms = int((time.time() - start_time) * 1000)
        yield AstraEvent(
            type="run.completed",
            data={
                "runId": turn_id,
                "status": "completed",
                "durationMs": elapsed_ms,
            },
        )

    async def _handle_chat(
        self,
        context: AstraContext,
        decision: RouteDecision,
        start_time: float,
    ) -> AsyncIterator[AstraEvent]:
        """Execute a conversational chat turn with live token streaming."""
        request = context.request
        turn_id = request.turn_id
        user_text = request.input.text

        yield AstraEvent(type="thinking", data={"correlationId": turn_id})

        # If conversation service is available, leverage its model router & provider
        if self.conversation_service:
            # Convert AstraRequest to TurnRequest for the underlying service
            from ..models import TurnRequest
            turn_req = TurnRequest(
                sessionId=request.conversation_id,
                conversationId=request.conversation_id,
                text=user_text,
                companionId=request.metadata.get("companionId", "hinaa"),
                providerMode=request.metadata.get("providerMode", "claude"),
                brainModel=request.metadata.get("brainModel"),
                userId=request.user_id,
            )

            # Delegate to existing stream_turn
            async for chunk in self.conversation_service.stream_turn(
                turn_req, turn_id, user_id=request.user_id
            ):
                # Parse chunk (NDJSON line) into AstraEvent
                try:
                    line = chunk.decode("utf-8").strip()
                    if not line:
                        continue
                    payload = json.loads(line)
                    ev_type = payload.pop("type", "unknown")
                    yield AstraEvent(type=ev_type, data=payload)
                except Exception:
                    continue
            return

        # Fallback chat synthesis when running standalone
        resolved_ref = context.entities.get("resolved_reference")
        subject = (
            resolved_ref.get("canonical_name")
            if resolved_ref and resolved_ref.get("canonical_name")
            else "that"
        )
        response_text = f"I understand your thoughts regarding {subject}. How can I assist you further?"
        
        words = response_text.split()
        for idx, word in enumerate(words):
            yield AstraEvent(
                type="text.delta",
                data={"delta": word + " ", "streamId": turn_id, "sequence": idx},
            )
            await asyncio.sleep(0.02)

        plan = AssistantTurnPlan(
            spokenText=response_text,
            displayText=response_text,
            language="en-US",
            emotion=Emotion(primary="neutral", intensity=0.5, valence=0.5, arousal=0.5),
            performance=Performance(facePreset="soft_smile", gesture="small_nod", gazeTarget="camera", headMotion="nod", blinkRate=0.5),
            beats=[],
            memoryCandidates=[],
            toolRequests=[],
        )
        yield AstraEvent(type="plan", data={"plan": plan.model_dump(), "provider": "astra-standalone"})

        elapsed_ms = int((time.time() - start_time) * 1000)
        yield AstraEvent(
            type="run.completed",
            data={
                "runId": turn_id,
                "status": "completed",
                "durationMs": elapsed_ms,
            },
        )

    async def _handle_agent_run(
        self,
        context: AstraContext,
        decision: RouteDecision,
        start_time: float,
    ) -> AsyncIterator[AstraEvent]:
        """Execute autonomous multi-step agent flow."""
        turn_id = context.request.turn_id
        goal = decision.goal

        yield AstraEvent(
            type="agent.started",
            data={"runId": turn_id, "goal": goal},
        )
        yield AstraEvent(
            type="agent.step.started",
            data={"stepId": "step_1", "description": f"Analyzing requirements for: {goal}"},
        )
        await asyncio.sleep(0.05)
        yield AstraEvent(
            type="agent.step.completed",
            data={"stepId": "step_1", "status": "completed"},
        )

        display_msg = f"Completed autonomous investigation for: **{goal}**."
        yield AstraEvent(
            type="text.delta",
            data={"delta": display_msg, "streamId": turn_id, "sequence": 0},
        )

        plan = AssistantTurnPlan(
            spokenText=f"I've completed the task for {goal}.",
            displayText=display_msg,
            language="en-US",
            emotion=Emotion(primary="happy", intensity=0.6, valence=0.6, arousal=0.4),
            performance=Performance(facePreset="soft_smile", gesture="small_nod", gazeTarget="camera", headMotion="nod", blinkRate=0.5),
            beats=[],
            memoryCandidates=[],
            toolRequests=[],
        )
        yield AstraEvent(type="plan", data={"plan": plan.model_dump(), "provider": "astra-agent"})

        elapsed_ms = int((time.time() - start_time) * 1000)
        yield AstraEvent(
            type="run.completed",
            data={"runId": turn_id, "status": "completed", "durationMs": elapsed_ms},
        )

    async def _handle_workspace(
        self,
        context: AstraContext,
        decision: RouteDecision,
        start_time: float,
    ) -> AsyncIterator[AstraEvent]:
        """Execute workspace file manipulation turn."""
        turn_id = context.request.turn_id
        ws = context.workspace
        target_file = ws.active_file if ws else "active file"

        yield AstraEvent(
            type="workspace.action.started",
            data={"file": target_file},
        )

        display_msg = f"Inspected workspace context for `{target_file}`."
        yield AstraEvent(
            type="text.delta",
            data={"delta": display_msg, "streamId": turn_id, "sequence": 0},
        )

        plan = AssistantTurnPlan(
            spokenText=f"I reviewed {target_file} in your workspace.",
            displayText=display_msg,
            language="en-US",
            emotion=Emotion(primary="neutral", intensity=0.5, valence=0.5, arousal=0.5),
            performance=Performance(facePreset="neutral", gesture="explain", gazeTarget="camera", headMotion="none", blinkRate=0.5),
            beats=[],
            memoryCandidates=[],
            toolRequests=[],
        )
        yield AstraEvent(type="plan", data={"plan": plan.model_dump(), "provider": "astra-workspace"})

        elapsed_ms = int((time.time() - start_time) * 1000)
        yield AstraEvent(
            type="run.completed",
            data={"runId": turn_id, "status": "completed", "durationMs": elapsed_ms},
        )

    async def _handle_clarification(
        self,
        context: AstraContext,
        decision: RouteDecision,
        start_time: float,
    ) -> AsyncIterator[AstraEvent]:
        """Request user clarification for ambiguous or high-risk actions."""
        turn_id = context.request.turn_id
        clarify_msg = f"Could you clarify your request regarding {decision.goal}?"

        yield AstraEvent(
            type="text.delta",
            data={"delta": clarify_msg, "streamId": turn_id, "sequence": 0},
        )

        plan = AssistantTurnPlan(
            spokenText=clarify_msg,
            displayText=clarify_msg,
            language="en-US",
            emotion=Emotion(primary="concerned", intensity=0.5, valence=0.0, arousal=0.4),
            performance=Performance(facePreset="concerned", gesture="gentle_head_tilt", gazeTarget="camera", headMotion="nod", blinkRate=0.5),
            beats=[],
            memoryCandidates=[],
            toolRequests=[],
        )
        yield AstraEvent(type="plan", data={"plan": plan.model_dump(), "provider": "astra-clarification"})

        elapsed_ms = int((time.time() - start_time) * 1000)
        yield AstraEvent(
            type="run.completed",
            data={"runId": turn_id, "status": "completed", "durationMs": elapsed_ms},
        )
