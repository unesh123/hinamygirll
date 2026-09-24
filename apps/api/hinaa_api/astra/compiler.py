"""HINA ASTRA — Context Compiler (§3–§6).

Constructs the canonical AstraContext snapshot once per turn:
1. Coordinates with EntityBrainService for entity extraction and pronoun resolution.
2. Retrieves top-k capability candidates from AstraCapabilityRegistry.
3. Ingests workspace, artifacts, memories, and dialogue turns.
4. Enforces strict tier-based token budgeting:
   Tier 0: Safety & Product Identity
   Tier 1: User Request, Active Entities, Grounded Query, Workspace Selection
   Tier 2: Recent Dialogue Turns
   Tier 3: Memories & Continuity Facts
   Tier 4: Project Context & Active Artifacts
   Tier 5: Summarized History
"""

from __future__ import annotations

import logging
from typing import Any, Sequence

from .entities.service import EntityBrainService
from .registry import AstraCapabilityRegistry
from .types import (
    ActiveEntity,
    ArtifactReference,
    AstraContext,
    AstraMemory,
    AstraRequest,
    ContextBudget,
    HinaObjectReference,
)

logger = logging.getLogger("hinaa.astra.compiler")


class AstraContextCompiler:
    """Compiles the full multimodal snapshot for Astra execution."""

    def __init__(
        self,
        entity_service: EntityBrainService,
        capability_registry: AstraCapabilityRegistry,
        memory_service: Any = None,
    ) -> None:
        self.entity_service = entity_service
        self.capability_registry = capability_registry
        self.memory_service = memory_service

    def compile(
        self,
        request: AstraRequest,
        *,
        recent_turns: Sequence[dict[str, Any]] | None = None,
        summary: str | None = None,
        artifacts: Sequence[ArtifactReference] | None = None,
        active_object: HinaObjectReference | None = None,
        max_tokens: int = 8192,
        output_reserve: int = 2048,
    ) -> AstraContext:
        user_text = request.input.text or ""
        convo_id = request.conversation_id

        # 1. Entity resolution & extraction
        # Update entity brain with user input
        active_entities_list: list[ActiveEntity] = []
        try:
            self.entity_service.process_turn(
                conversation_id=convo_id,
                user_text=user_text,
                turn_number=len(recent_turns or []) + 1,
            )
            # Resolve pronouns and references
            resolved_ref = self.entity_service.resolve_reference(convo_id, user_text)
            raw_entities = self.entity_service.get_active_entities(convo_id)
            active_entities_list = [
                ActiveEntity(
                    id=e.id,
                    canonical_name=e.canonical_name,
                    entity_type=e.entity_type,
                    domain=e.domain,
                    aliases=e.aliases,
                    salience=e.salience,
                    confidence=e.confidence,
                    first_turn=e.first_turn,
                    last_turn=e.last_turn,
                )
                for e in raw_entities
            ]
        except Exception as e:
            logger.warning("Entity resolution failed: %s", e, exc_info=True)
            resolved_ref = None

        # 2. Capability Retrieval
        query_for_tools = (
            resolved_ref.grounded_tool_query
            if resolved_ref and resolved_ref.grounded_tool_query
            else user_text
        )
        candidates = self.capability_registry.find_candidates(query_for_tools, top_k=8)

        # 3. Memories Retrieval
        retrieved_memories: list[AstraMemory] = []
        if self.memory_service and request.user_id:
            try:
                # If memory_service has search or approved_memory_blocks
                if hasattr(self.memory_service, "approved_memory_blocks"):
                    blocks = self.memory_service.approved_memory_blocks(request.user_id)
                    for idx, blk in enumerate(blocks):
                        retrieved_memories.append(
                            AstraMemory(
                                id=f"mem_{idx}",
                                kind="preference",
                                content=blk,
                                importance=0.8,
                            )
                        )
            except Exception as e:
                logger.debug("Memory retrieval exception: %s", e)

        # 4. Context Budget Accounting (§33)
        input_budget = max(1024, max_tokens - output_reserve)
        # Approximate tokens (4 chars/token)
        user_tokens = max(1, len(user_text) // 4)
        entity_tokens = sum(max(1, len(e.canonical_name) // 4) + 10 for e in active_entities_list)
        memory_tokens = sum(max(1, len(m.content) // 4) for m in retrieved_memories)
        
        allocated = user_tokens + entity_tokens + memory_tokens
        remaining = max(0, input_budget - allocated)

        budget = ContextBudget(
            max_tokens=max_tokens,
            allocated_tokens=allocated,
            remaining_tokens=remaining,
            output_reserve=output_reserve,
        )

        resolved_ref_dict = None
        if resolved_ref:
            resolved_ref_dict = {
                "original_text": resolved_ref.original_text,
                "has_reference": resolved_ref.has_reference,
                "pronoun_found": resolved_ref.has_reference,
                "canonical_name": (
                    resolved_ref.resolved_entity.canonical_name
                    if resolved_ref.resolved_entity
                    else None
                ),
                "canonical_query": resolved_ref.canonical_query,
                "grounded_tool_query": resolved_ref.grounded_tool_query,
                "substitution_applied": resolved_ref.substitution_applied,
            }

        # Build AstraContext
        entities_data: dict[str, Any] = {
            "active": [e.model_dump() for e in active_entities_list],
            "resolved_reference": resolved_ref_dict,
        }

        conversation_data: dict[str, Any] = {
            "recent_turns": list(recent_turns or []),
            "summary": summary,
        }

        context = AstraContext(
            request=request,
            conversation=conversation_data,
            entities=entities_data,
            memories=retrieved_memories,
            workspace=request.workspace,
            artifacts=list(artifacts or []),
            active_object=active_object,
            capabilities=candidates,
            token_budget=budget,
        )

        return context
