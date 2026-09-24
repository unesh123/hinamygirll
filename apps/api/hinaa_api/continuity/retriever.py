from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any
from sqlalchemy import desc, or_, select
from sqlalchemy.orm import Session, sessionmaker

from ..media.asset_store import get_asset_store
from ..persistence.orm import (
    Conversation,
    ConversationEntity,
    ConversationSummary,
    DurableTask,
    EpisodicMemory,
    ExplicitMemory,
    Message,
    UserContinuityState,
)
from .models import MemoryEvidence, MemoryScope, UserContinuitySnapshot

logger = logging.getLogger("hinaa.continuity.retriever")

HISTORICAL_QUERY_RE = re.compile(
    r"\b(?:what (?:were we talking|did (?:we|i) (?:talk|say|discuss)|was that)|remember (?:when|that)|yesterday|last week|earlier|previously|before)\b",
    re.IGNORECASE,
)
EXACT_QUOTE_RE = re.compile(
    r"\b(?:what exactly did i say|exact words|quote me|verbatim)\b",
    re.IGNORECASE,
)
CONTINUE_TASK_RE = re.compile(
    r"\b(?:continue|resume|pick up|proceed with)\b",
    re.IGNORECASE,
)


class CrossSessionMemoryRetriever:
    """Retrieves relevant context, assets, project decisions, and historical episodes across sessions."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._factory = session_factory

    def get_continuity_snapshot(self, owner_id: str) -> UserContinuitySnapshot:
        """Fetch the compact materialized continuity snapshot for a user."""
        with self._factory() as session:
            state = session.scalar(select(UserContinuityState).where(UserContinuityState.owner_id == owner_id))
            if not state:
                return UserContinuitySnapshot(owner_id=owner_id)

            def _parse(val: str | None, default: Any) -> Any:
                if not val:
                    return default
                try:
                    return json.loads(val)
                except Exception:
                    return default

            return UserContinuitySnapshot(
                owner_id=state.owner_id,
                tenant_id=state.tenant_id,
                preferred_name=state.preferred_name,
                language_preferences=_parse(state.language_preferences_json, ["en-US"]),
                communication_style=state.communication_style,
                verbosity_preferences=state.verbosity_preferences,
                important_entities=_parse(state.important_entities_json, []),
                important_projects=_parse(state.important_projects_json, []),
                recent_projects=_parse(state.recent_projects_json, []),
                recurring_topics=_parse(state.recurring_topics_json, []),
                active_long_running_tasks=_parse(state.active_long_running_tasks_json, []),
                recent_conversation_ids=_parse(state.recent_conversation_ids_json, []),
                recent_asset_ids=_parse(state.recent_asset_ids_json, []),
                approved_asset_ids=_parse(state.approved_asset_ids_json, []),
                persistent_preferences=_parse(state.persistent_preferences_json, []),
                relationship_context=_parse(state.relationship_context_json, {}),
                last_interaction_at=state.last_interaction_at,
                memory_revision=state.memory_revision,
            )

    def retrieve_relevant_context(
        self,
        owner_id: str,
        text: str,
        *,
        conversation_id: str | None = None,
        project_id: str | None = None,
        active_entities: list[str] | None = None,
        limit: int = 8,
    ) -> list[MemoryEvidence]:
        """Main multi-tier cross-session retrieval method."""
        if not owner_id:
            return []

        evidence: list[MemoryEvidence] = []
        lowered = text.lower()
        is_historical = bool(HISTORICAL_QUERY_RE.search(text))
        is_exact_quote = bool(EXACT_QUOTE_RE.search(text))
        is_continue = bool(CONTINUE_TASK_RE.search(text))

        with self._factory() as session:
            snapshot = self.get_continuity_snapshot(owner_id)

            # ── 1. Approved Entity Assets & Character References ───────────────
            # e.g. "generate Hina" or "Hina's face"
            for ent in snapshot.important_entities:
                name = ent.get("name", "")
                norm = ent.get("normalized", name.lower())
                if norm and (norm in lowered or any(a.lower() in lowered for a in [name])):
                    appr_face = ent.get("approved_face") or ent.get("approved_reference")
                    if appr_face:
                        evidence.append(
                            MemoryEvidence(
                                source_type="approved_asset",
                                source_id=appr_face,
                                scope=MemoryScope.USER_GLOBAL,
                                content=f"Approved face reference for {name} is {appr_face}",
                                score=1.5,
                                confidence=1.0,
                                entity_id=name,
                                metadata={"asset_id": appr_face, "entity": name},
                            )
                        )

            # ── 2. Cross-Session Asset Selection ───────────────────────────────
            # e.g. "use that Gojo image I picked before"
            if any(k in lowered for k in ("image i picked", "image i chose", "selected image", "image we chose", "gojo image")):
                asset_store = get_asset_store()
                # Check for assets tagged with selected or entity
                matched_assets = asset_store.query_assets(owner_id=owner_id, limit=10)
                for a in matched_assets:
                    tag_match = any(t.lower() in lowered for t in a.tags if len(t) > 2)
                    filename_match = bool(
                        a.filename and any(part in lowered for part in a.filename.lower().replace(".", "_").split("_") if len(part) > 3)
                    )

                    score = 1.3
                    if tag_match or filename_match:
                        score += 0.5
                    elif not (a.approval_state in ("approved", "selected")):
                        continue

                    evidence.append(
                        MemoryEvidence(
                            source_type="selected_asset",
                            source_id=a.id,
                            scope=MemoryScope.USER_GLOBAL,
                            content=f"Previously selected asset {a.id} ({a.filename or 'image'})",
                            score=score,
                            confidence=0.95,
                            metadata={"asset_id": a.id, "filename": a.filename, "url": a.public_url},
                        )
                    )

            # ── 3. Project Decisions & Architecture Facts ──────────────────────
            # e.g. "What database are we using on Nova?"
            # Extract possible project names
            project_names = list(snapshot.important_projects)
            if project_id and project_id not in project_names:
                project_names.append(project_id)
            # Also detect words that look like project names (e.g. "Nova")
            for token in re.findall(r"\b[A-Z][a-zA-Z0-9_-]+\b", text):
                if token.lower() not in {"what", "how", "why", "where", "who", "when", "can", "the", "generate", "hina"}:
                    project_names.append(token)

            for p_name in set(project_names):
                if p_name.lower() in lowered or (project_id and p_name.lower() == project_id.lower()):
                    # Query project facts from explicit_memories
                    proj_mems = session.scalars(
                        select(ExplicitMemory)
                        .where(
                            ExplicitMemory.user_id == owner_id,
                            ExplicitMemory.deleted_at.is_(None),
                            ExplicitMemory.status == "approved",
                            or_(
                                ExplicitMemory.project_id == p_name,
                                ExplicitMemory.content.ilike(f"%{p_name}%"),
                            ),
                        )
                    ).all()
                    for pm in proj_mems:
                        evidence.append(
                            MemoryEvidence(
                                source_type="project",
                                source_id=pm.id,
                                scope=MemoryScope.PROJECT,
                                content=pm.content,
                                score=1.4,
                                confidence=1.0,
                                project_id=p_name,
                                source_conversation_id=pm.source_turn_ref,
                            )
                        )

            # ── 4. Unfinished Task Continuation ────────────────────────────────
            # e.g. "continue our Nova work" or "continue what we were doing"
            if is_continue:
                task_query = (
                    select(DurableTask)
                    .where(
                        DurableTask.owner_id == owner_id,
                        DurableTask.status.not_in(["succeeded", "failed", "cancelled"]),
                    )
                    .order_by(DurableTask.updated_at.desc())
                    .limit(5)
                )
                tasks = session.scalars(task_query).all()
                for t in tasks:
                    score = 1.2
                    # Boost if project or title matches text
                    if t.project_id and t.project_id.lower() in lowered:
                        score += 0.5
                    if any(w in lowered for w in t.goal.lower().split() if len(w) > 3):
                        score += 0.3
                    evidence.append(
                        MemoryEvidence(
                            source_type="unfinished_task",
                            source_id=t.id,
                            scope=MemoryScope.PROJECT if t.project_id else MemoryScope.USER_GLOBAL,
                            content=f"Unfinished task {t.id}: {t.goal} (status: {t.status})",
                            score=score,
                            confidence=0.9,
                            project_id=t.project_id,
                            source_conversation_id=t.conversation_id,
                            metadata={"task_id": t.id, "goal": t.goal, "status": t.status},
                        )
                    )

            # ── 5. Exact Quotation / Verbatim Recall ───────────────────────────
            # e.g. "What exactly did I say?"
            if is_exact_quote:
                recent_msgs = session.scalars(
                    select(Message)
                    .join(Conversation, Message.conversation_id == Conversation.id)
                    .where(
                        Conversation.user_id == owner_id,
                        Message.role == "user",
                        Message.deleted_at.is_(None),
                    )
                    .order_by(Message.created_at.desc())
                    .limit(10)
                ).all()
                for m in recent_msgs:
                    if conversation_id and m.conversation_id == conversation_id:
                        continue
                    evidence.append(
                        MemoryEvidence(
                            source_type="message",
                            source_id=m.id,
                            scope=MemoryScope.CONVERSATION,
                            content=f'User stated: "{m.content}"',
                            score=1.6,
                            confidence=1.0,
                            source_conversation_id=m.conversation_id,
                            metadata={"exact_quote": m.content, "message_id": m.id},
                        )
                    )
                    break  # Most recent past utterance

            # ── 6. Historical Conversation Recall by Topic ─────────────────────
            # e.g. "what were we talking about when I mentioned Kung Fu Panda?"
            # Extract keywords excluding stopwords
            stopwords = {"what", "were", "talking", "about", "when", "mentioned", "did", "say", "tell", "you", "hina", "the", "that", "this", "our", "with"}
            tokens = [w for w in re.findall(r"\b[a-zA-Z]{3,}\b", lowered) if w not in stopwords]

            if is_historical or tokens:
                for token in tokens:
                    # Search ConversationSummary
                    summaries = session.scalars(
                        select(ConversationSummary)
                        .join(Conversation, ConversationSummary.conversation_id == Conversation.id)
                        .where(
                            Conversation.user_id == owner_id,
                            ConversationSummary.summary.ilike(f"%{token}%"),
                        )
                        .order_by(ConversationSummary.created_at.desc())
                        .limit(3)
                    ).all()
                    for s in summaries:
                        if conversation_id and s.conversation_id == conversation_id:
                            continue
                        evidence.append(
                            MemoryEvidence(
                                source_type="conversation_summary",
                                source_id=s.id,
                                scope=MemoryScope.USER_GLOBAL,
                                content=f"Prior conversation summary: {s.summary[:200]}",
                                score=1.3,
                                confidence=0.85,
                                source_conversation_id=s.conversation_id,
                            )
                        )

                    # Search EpisodicMemory
                    episodes = session.scalars(
                        select(EpisodicMemory)
                        .where(
                            EpisodicMemory.user_id == owner_id,
                            EpisodicMemory.event.ilike(f"%{token}%"),
                        )
                        .order_by(EpisodicMemory.created_at.desc())
                        .limit(3)
                    ).all()
                    for ep in episodes:
                        if conversation_id and ep.conversation_id == conversation_id:
                            continue
                        evidence.append(
                            MemoryEvidence(
                                source_type="episodic_memory",
                                source_id=ep.id,
                                scope=MemoryScope.USER_GLOBAL,
                                content=f"Prior episode: {ep.event}",
                                score=1.2,
                                confidence=0.85,
                                source_conversation_id=ep.conversation_id,
                            )
                        )

            # ── 7. Global Semantic & Procedural Memories ───────────────────────
            # Filter active vs superseded depending on query intent
            allow_superseded = "before" in lowered or "previously" in lowered or "used to" in lowered or "what color did we use" in lowered
            status_filter = ("approved", "superseded") if allow_superseded else ("approved",)

            all_explicit = session.scalars(
                select(ExplicitMemory)
                .where(
                    ExplicitMemory.user_id == owner_id,
                    ExplicitMemory.deleted_at.is_(None),
                    ExplicitMemory.status.in_(status_filter),
                )
                .order_by(ExplicitMemory.updated_at.desc())
                .limit(20)
            ).all()

            for mem in all_explicit:
                # Calculate keyword overlap
                mem_lowered = mem.content.lower()
                overlap = any(t in mem_lowered for t in tokens) if tokens else False
                is_pref = mem.category in ("preference", "procedural", "workflow", "correction")

                score = 0.8
                if mem.status == "superseded":
                    if allow_superseded:
                        score = 1.1
                    else:
                        continue  # Skip superseded unless explicitly asking about historical/past state
                elif overlap:
                    score = 1.3
                elif is_pref:
                    score = 1.0

                evidence.append(
                    MemoryEvidence(
                        source_type="semantic_memory",
                        source_id=mem.id,
                        scope=MemoryScope.USER_GLOBAL if mem.scope == "user_global" else MemoryScope.PROJECT,
                        content=f"{mem.content} (status: {mem.status})",
                        score=score,
                        confidence=1.0,
                        project_id=mem.project_id,
                        entity_id=mem.entity_id,
                        source_conversation_id=mem.source_turn_ref,
                    )
                )

        # Multi-Project Isolation: If an active project is set, exclude conflicting other projects
        filtered_evidence: list[MemoryEvidence] = []
        for ev in evidence:
            if project_id and ev.project_id and ev.project_id.lower() != project_id.lower():
                # Belongs to a different project; isolate
                continue
            filtered_evidence.append(ev)

        # Deduplicate evidence by content
        unique_evidence: list[MemoryEvidence] = []
        seen: set[str] = set()
        for ev in sorted(filtered_evidence, key=lambda e: e.score, reverse=True):
            key = ev.content.strip().lower()
            if key not in seen:
                seen.add(key)
                unique_evidence.append(ev)

        return unique_evidence[:limit]
