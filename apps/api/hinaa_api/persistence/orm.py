from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    auth_subject: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(40), default="active")
    memory_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    memories: Mapped[list[ExplicitMemory]] = relationship(back_populates="user")
    consents: Mapped[list[MemoryConsent]] = relationship(back_populates="user")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    companion_id: Mapped[str] = mapped_column(String(20))
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    messages: Mapped[list[Message]] = relationship(back_populates="conversation")
    summaries: Mapped[list[ConversationSummary]] = relationship(back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))
    # content stores the full Canonical Turn Record (AssistantTurnPlan JSON) for assistant, or text for user.
    content: Mapped[str] = mapped_column(Text())
    language: Mapped[str] = mapped_column(String(20), default="mixed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    attachments: Mapped[list[MessageAttachment]] = relationship(
        back_populates="message", cascade="all, delete-orphan", order_by="MessageAttachment.ordinal"
    )


class MessageAttachment(Base):
    __tablename__ = "message_attachments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    message_id: Mapped[str] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), index=True
    )
    asset_id: Mapped[str] = mapped_column(String(64), index=True)
    kind: Mapped[str] = mapped_column(String(30), default="image")
    mime_type: Mapped[str] = mapped_column(String(100), default="image/png")
    filename: Mapped[str] = mapped_column(String(255), default="attachment")
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    sha256: Mapped[str] = mapped_column(String(64), default="")
    ordinal: Mapped[int] = mapped_column(Integer, default=0)
    role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    message: Mapped[Message] = relationship(back_populates="attachments")


class ConversationSummary(Base):
    __tablename__ = "conversation_summaries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    summary: Mapped[str] = mapped_column(Text())
    topics_json: Mapped[str] = mapped_column(Text(), default="[]")
    entities_json: Mapped[str] = mapped_column(Text(), default="[]")
    decisions_json: Mapped[str] = mapped_column(Text(), default="[]")
    version: Mapped[int] = mapped_column(default=1)
    generated: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped[Conversation] = relationship(back_populates="summaries")


class ExplicitMemory(Base):
    __tablename__ = "explicit_memories"
    __table_args__ = (UniqueConstraint("user_id", "normalized_hash", name="uq_user_memory_hash"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text())
    normalized_hash: Mapped[str] = mapped_column(String(64), index=True)
    category: Mapped[str] = mapped_column(String(40), default="other")
    scope: Mapped[str] = mapped_column(String(40), default="user_global")
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    entity_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(40), default="approved")  # pending|approved|revoked|superseded
    superseded_by_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    consent_state: Mapped[str] = mapped_column(String(40), default="explicit")
    source_turn_ref: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="memories")


class MemoryConsent(Base):
    __tablename__ = "memory_consents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(40))
    policy_version: Mapped[str] = mapped_column(String(40), default="privacy-1.0.0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="consents")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    action: Mapped[str] = mapped_column(String(100))
    resource_type: Mapped[str] = mapped_column(String(50))
    resource_id: Mapped[str] = mapped_column(String(36))
    result: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GenerationSet(Base):
    __tablename__ = "generation_sets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    conversation_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("conversations.id"), index=True, nullable=True)
    prompt: Mapped[str] = mapped_column(Text())
    workflow_mode: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    jobs: Mapped[list[ImageJob]] = relationship(
        "ImageJob", back_populates="generation_set", cascade="all, delete-orphan"
    )


class ImageJob(Base):
    __tablename__ = "image_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    generation_set_id: Mapped[str] = mapped_column(String(36), ForeignKey("generation_sets.id"), index=True)
    comfy_prompt_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    seed: Mapped[int] = mapped_column(BigInteger())
    status: Mapped[str] = mapped_column(String(50), default="pending") # pending, processing, completed, failed, cancelled
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True) # local absolute path
    width: Mapped[int] = mapped_column(Integer(), default=1024)
    height: Mapped[int] = mapped_column(Integer(), default=1024)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    generation_set: Mapped[GenerationSet] = relationship(
        "GenerationSet", back_populates="jobs"
    )


class LocalProject(Base):
    __tablename__ = "local_projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text(), default="")
    root_path: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(30), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LocalProjectFile(Base):
    __tablename__ = "local_project_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("local_projects.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(120), default="application/octet-stream")
    relative_path: Mapped[str] = mapped_column(String(600))
    size_bytes: Mapped[int] = mapped_column(BigInteger(), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LocalProjectArtifact(Base):
    __tablename__ = "local_project_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("local_projects.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(50))  # note|research|image|document|export|link
    title: Mapped[str] = mapped_column(String(240))
    content: Mapped[str] = mapped_column(Text(), default="")
    relative_path: Mapped[str | None] = mapped_column(String(600), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1200), nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text(), default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LocalProjectTask(Base):
    __tablename__ = "local_project_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("local_projects.id", ondelete="CASCADE"), index=True
    )
    parent_task_id: Mapped[str | None] = mapped_column(
        ForeignKey("local_project_tasks.id", ondelete="CASCADE"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(240))
    detail: Mapped[str] = mapped_column(Text(), default="")
    status: Mapped[str] = mapped_column(String(30), default="pending")
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    position: Mapped[int] = mapped_column(Integer(), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LocalAgentRun(Base):
    """A transparent local execution record for a project-scoped Hinaa run."""

    __tablename__ = "local_agent_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("local_projects.id", ondelete="CASCADE"), index=True
    )
    root_task_id: Mapped[str | None] = mapped_column(
        ForeignKey("local_project_tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    goal: Mapped[str] = mapped_column(Text())
    status: Mapped[str] = mapped_column(String(30), default="queued")
    summary: Mapped[str] = mapped_column(Text(), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LocalAgentRunEvent(Base):
    """Append-only history that makes local agent behavior inspectable and resumable."""

    __tablename__ = "local_agent_run_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("local_agent_runs.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer(), default=0)
    kind: Mapped[str] = mapped_column(String(40), default="status")
    status: Mapped[str] = mapped_column(String(30), default="queued")
    label: Mapped[str] = mapped_column(String(240))
    detail: Mapped[str] = mapped_column(Text(), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProviderUsage(Base):
    """Tracks credit consumption and latency per provider and operation."""

    __tablename__ = "provider_usage"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    provider: Mapped[str] = mapped_column(String(50), index=True)
    operation: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(100))
    credits: Mapped[int] = mapped_column(Integer(), default=1)
    status: Mapped[str] = mapped_column(String(30), default="success")
    latency_ms: Mapped[int] = mapped_column(Integer(), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class AgentRunRecord(Base):
    __tablename__ = "agent_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    conversation_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    goal: Mapped[str] = mapped_column(Text())
    status: Mapped[str] = mapped_column(String(30), default="queued")
    failure_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text(), nullable=True)
    maximum_steps: Mapped[int] = mapped_column(Integer(), default=12)
    maximum_replans: Mapped[int] = mapped_column(Integer(), default=2)
    replan_count: Mapped[int] = mapped_column(Integer(), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text(), default="{}")


class AgentPlanRecord(Base):
    __tablename__ = "agent_plans"

    plan_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("agent_runs.run_id", ondelete="CASCADE"), index=True)
    goal: Mapped[str] = mapped_column(Text())
    version: Mapped[int] = mapped_column(Integer(), default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentStepRecord(Base):
    __tablename__ = "agent_plan_steps"

    step_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    plan_id: Mapped[str] = mapped_column(String(64), ForeignKey("agent_plans.plan_id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer(), default=0)
    title: Mapped[str] = mapped_column(String(255))
    operation_type: Mapped[str] = mapped_column(String(50), default="respond")
    tool_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    parameters_json: Mapped[str] = mapped_column(Text(), default="{}")
    state: Mapped[str] = mapped_column(String(30), default="pending")
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed_by_user: Mapped[bool] = mapped_column(Boolean, default=False)
    attempt_count: Mapped[int] = mapped_column(Integer(), default=0)
    max_attempts: Mapped[int] = mapped_column(Integer(), default=2)
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    dependencies_json: Mapped[str] = mapped_column(Text(), default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentEventRecord(Base):
    __tablename__ = "agent_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("agent_runs.run_id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer(), default=0)
    event_type: Mapped[str] = mapped_column(String(60))
    step_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload_json: Mapped[str] = mapped_column(Text(), default="{}")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConversationTurnState(Base):
    """Durable per-conversation dialogue state — persisted every turn, survives
    tool failures, provider switches, and server restarts.

    JSON columns use compact dicts so the full row stays under ~8 KB even for
    long multi-step tasks.  ``state_version`` lets the reader detect schema
    evolution without a migration lock.
    """

    __tablename__ = "conversation_turn_states"

    # Primary key: the conversation_id from the frontend (UUID or slug).
    # One row per conversation — upserted on every turn, not appended.
    conversation_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    state_version: Mapped[int] = mapped_column(Integer(), default=1)

    # ── Active topic / intent ─────────────────────────────────────────────────
    active_topic: Mapped[str | None] = mapped_column(String(240), nullable=True)
    active_intent: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # ── Typed slots (JSON dict: slot_name → {value, type, confidence}) ────────
    slots_json: Mapped[str] = mapped_column(Text(), default="{}")

    # ── Pending dialogue stack items (JSON objects) ───────────────────────────
    pending_question_json: Mapped[str | None] = mapped_column(Text(), nullable=True)
    pending_confirmation_json: Mapped[str | None] = mapped_column(Text(), nullable=True)
    pending_action_json: Mapped[str | None] = mapped_column(Text(), nullable=True)

    # ── Tool continuation state ───────────────────────────────────────────────
    last_tool_state_json: Mapped[str | None] = mapped_column(Text(), nullable=True)

    # ── Active entities (JSON list of {type, name, normalized}) ──────────────
    active_entities_json: Mapped[str] = mapped_column(Text(), default="[]")

    # ── Dialogue act of the most recent user turn ─────────────────────────────
    last_dialogue_act: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # ── Unresolved references pending slot resolution ─────────────────────────
    unresolved_refs_json: Mapped[str] = mapped_column(Text(), default="[]")

    # ── Action & Asset Ledger (P0 Real Runtime Repair) ────────────────────────
    # Tracks the most recent action executed by the assistant (e.g. image generation)
    last_assistant_action_json: Mapped[str | None] = mapped_column(Text(), nullable=True)
    # List of asset IDs generated during this conversation
    last_generated_asset_ids_json: Mapped[str] = mapped_column(Text(), default="[]")
    # All active conversation assets (uploaded, attached, searched, generated)
    active_assets_json: Mapped[str] = mapped_column(Text(), default="[]")
    # Ordered search/generation result sets (e.g. {result_set_id, ordered_asset_ids})
    tool_result_sets_json: Mapped[str] = mapped_column(Text(), default="[]")
    # Exact user/UI-selected gallery asset ({asset_id, result_set_id, ordinal_index, source})
    selected_asset_json: Mapped[str | None] = mapped_column(Text(), nullable=True)

    # ── Active Goal & Hard Constraints (P0 Continuous Intelligence) ──────────
    active_goal_json: Mapped[str | None] = mapped_column(Text(), nullable=True)

    # ── Turn counter for decay / compaction logic ─────────────────────────────
    turn_count: Mapped[int] = mapped_column(Integer(), default=0)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ConversationEntity(Base):
    __tablename__ = "conversation_entities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    entity_type: Mapped[str] = mapped_column(String(50))
    display_name: Mapped[str] = mapped_column(String(240))
    normalized_name: Mapped[str] = mapped_column(String(240), index=True)
    aliases_json: Mapped[str] = mapped_column(Text(), default="[]")
    source_message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    asset_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class EpisodicMemory(Base):
    __tablename__ = "episodic_memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    event: Mapped[str] = mapped_column(Text())
    event_type: Mapped[str] = mapped_column(String(50))
    source_message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    scope: Mapped[str] = mapped_column(String(40), default="conversation")
    importance: Mapped[int] = mapped_column(Integer(), default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TrainingExampleCandidate(Base):
    __tablename__ = "training_example_candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    source_message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    candidate_type: Mapped[str] = mapped_column(String(50), default="conversation_turn")
    input_text: Mapped[str] = mapped_column(Text())
    output_text: Mapped[str] = mapped_column(Text())
    metadata_json: Mapped[str] = mapped_column(Text(), default="{}")
    status: Mapped[str] = mapped_column(String(50), default="pending_review")
    quality_score: Mapped[int] = mapped_column(Integer(), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DurableTask(Base):
    __tablename__ = "durable_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(String(36), index=True)
    conversation_id: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)
    project_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    goal: Mapped[str] = mapped_column(Text())
    task_type: Mapped[str] = mapped_column(String(60), default="general")
    priority: Mapped[int] = mapped_column(Integer(), default=0)
    reasoning_mode: Mapped[str] = mapped_column(String(40), default="balanced")
    status: Mapped[str] = mapped_column(String(40), default="planning")
    version: Mapped[int] = mapped_column(Integer(), default=1)
    current_step_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    blocked_reason: Mapped[str | None] = mapped_column(Text(), nullable=True)
    failure_count: Mapped[int] = mapped_column(Integer(), default=0)
    checkpoint_version: Mapped[int] = mapped_column(Integer(), default=0)
    worker_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    lease_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    fencing_token: Mapped[int] = mapped_column(Integer(), default=0)
    lease_acquired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    metadata_json: Mapped[str] = mapped_column(Text(), default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DurableTaskStep(Base):
    __tablename__ = "durable_task_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("durable_tasks.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer(), default=0)
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text(), default="")
    status: Mapped[str] = mapped_column(String(40), default="pending")
    version: Mapped[int] = mapped_column(Integer(), default=1)
    dependencies_json: Mapped[str] = mapped_column(Text(), default="[]")
    attempt_count: Mapped[int] = mapped_column(Integer(), default=0)
    max_attempts: Mapped[int] = mapped_column(Integer(), default=3)
    retry_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tool_call_ids_json: Mapped[str] = mapped_column(Text(), default="[]")
    input_artifact_ids_json: Mapped[str] = mapped_column(Text(), default="[]")
    output_artifact_ids_json: Mapped[str] = mapped_column(Text(), default="[]")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text(), nullable=True)


class DurableTaskEvent(Base):
    __tablename__ = "durable_task_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("durable_tasks.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer(), default=0)
    event_type: Mapped[str] = mapped_column(String(60))
    step_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    payload_json: Mapped[str] = mapped_column(Text(), default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DurableTaskCheckpoint(Base):
    __tablename__ = "durable_task_checkpoints"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("durable_tasks.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer(), default=1)
    state_json: Mapped[str] = mapped_column(Text(), default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SideEffectJournal(Base):
    __tablename__ = "side_effect_journal"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_side_effect_idempotency_key"),)

    operation_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("durable_tasks.id", ondelete="CASCADE"), index=True)
    step_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), index=True)
    provider: Mapped[str] = mapped_column(String(80))
    operation_type: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(40), default="PLANNED", index=True)
    request_hash: Mapped[str] = mapped_column(String(64), default="")
    provider_operation_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    response_hash: Mapped[str] = mapped_column(String(64), default="")
    metadata_json: Mapped[str] = mapped_column(Text(), default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DurableOutboxEvent(Base):
    __tablename__ = "durable_outbox_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    aggregate_type: Mapped[str] = mapped_column(String(60), default="task")
    aggregate_id: Mapped[str] = mapped_column(String(80), index=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    payload_json: Mapped[str] = mapped_column(Text(), default="{}")
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer(), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DurableInboxEvent(Base):
    __tablename__ = "durable_inbox_events"
    __table_args__ = (UniqueConstraint("source", "external_event_id", name="uq_durable_inbox_external_event"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source: Mapped[str] = mapped_column(String(80), index=True)
    external_event_id: Mapped[str] = mapped_column(String(160), index=True)
    payload_hash: Mapped[str] = mapped_column(String(64), default="")
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DurableDeadLetter(Base):
    __tablename__ = "durable_dead_letters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    step_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    operation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    reason: Mapped[str] = mapped_column(Text())
    payload_json: Mapped[str] = mapped_column(Text(), default="{}")
    status: Mapped[str] = mapped_column(String(40), default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserContinuityState(Base):
    """Compact durable snapshot of a user's cross-session state, preferences, and entities."""
    __tablename__ = "user_continuity_states"

    owner_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    preferred_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    language_preferences_json: Mapped[str] = mapped_column(Text(), default="[]")
    communication_style: Mapped[str | None] = mapped_column(String(50), nullable=True)
    verbosity_preferences: Mapped[str | None] = mapped_column(String(50), nullable=True)

    important_entities_json: Mapped[str] = mapped_column(Text(), default="[]")
    important_projects_json: Mapped[str] = mapped_column(Text(), default="[]")
    recent_projects_json: Mapped[str] = mapped_column(Text(), default="[]")
    recurring_topics_json: Mapped[str] = mapped_column(Text(), default="[]")

    active_long_running_tasks_json: Mapped[str] = mapped_column(Text(), default="[]")
    recent_conversation_ids_json: Mapped[str] = mapped_column(Text(), default="[]")
    recent_asset_ids_json: Mapped[str] = mapped_column(Text(), default="[]")
    approved_asset_ids_json: Mapped[str] = mapped_column(Text(), default="[]")

    persistent_preferences_json: Mapped[str] = mapped_column(Text(), default="[]")
    relationship_context_json: Mapped[str] = mapped_column(Text(), default="{}")

    last_interaction_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    memory_revision: Mapped[int] = mapped_column(Integer(), default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ConversationEpisode(Base):
    """B2 summary tree (directive §17–§24) — one coherent episode of a conversation.

    An episode is a topic/task-coherent run of turns (NOT one per message).
    Summaries are retrieval aids; the original Message rows remain the source
    of truth and stay exactly retrievable (§21).
    """

    __tablename__ = "conversation_episodes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    start_sequence: Mapped[int] = mapped_column(Integer(), default=0)
    end_sequence: Mapped[int] = mapped_column(Integer(), default=0)

    topic_ids_json: Mapped[str] = mapped_column(Text(), default="[]")
    entity_ids_json: Mapped[str] = mapped_column(Text(), default="[]")
    project_ids_json: Mapped[str] = mapped_column(Text(), default="[]")
    task_ids_json: Mapped[str] = mapped_column(Text(), default="[]")
    asset_ids_json: Mapped[str] = mapped_column(Text(), default="[]")

    summary: Mapped[str] = mapped_column(Text(), default="")
    goals_json: Mapped[str] = mapped_column(Text(), default="[]")
    decisions_json: Mapped[str] = mapped_column(Text(), default="[]")
    corrections_json: Mapped[str] = mapped_column(Text(), default="[]")
    constraints_json: Mapped[str] = mapped_column(Text(), default="[]")
    open_questions_json: Mapped[str] = mapped_column(Text(), default="[]")
    unfinished_actions_json: Mapped[str] = mapped_column(Text(), default="[]")

    importance: Mapped[int] = mapped_column(Integer(), default=1)
    boundary_reason: Mapped[str | None] = mapped_column(String(60), nullable=True)
    summary_version: Mapped[int] = mapped_column(Integer(), default=1)
    last_summarized_sequence: Mapped[int] = mapped_column(Integer(), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )





