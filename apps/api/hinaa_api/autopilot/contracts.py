"""
HINAA OS — Phase 13: Autopilot Contracts & Data Models
Defines immutable types, enums, dataclasses, and state machines for persistent autonomous operations.
"""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


class ScheduleType(str, enum.Enum):
    ONE_SHOT = "ONE_SHOT"
    INTERVAL = "INTERVAL"
    CRON = "CRON"
    EVENT_TRIGGERED = "EVENT_TRIGGERED"
    CONDITION = "CONDITION"


class JobStatus(str, enum.Enum):
    CREATED = "CREATED"
    SCHEDULED = "SCHEDULED"
    READY = "READY"
    CLAIMED = "CLAIMED"
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    RETRY_PENDING = "RETRY_PENDING"
    RECOVERING = "RECOVERING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    BLOCKED_UNAVAILABLE = "BLOCKED_UNAVAILABLE"
    NEEDS_RECONCILIATION = "NEEDS_RECONCILIATION"


class MisfirePolicy(str, enum.Enum):
    COALESCE = "COALESCE"
    RUN_LATEST = "RUN_LATEST"
    SKIP = "SKIP"


class PermissionTier(str, enum.Enum):
    TIER_A = "TIER_A"  # Routine read-only / summarization / approved checks
    TIER_B = "TIER_B"  # Scoped reversible sandbox changes
    TIER_C = "TIER_C"  # Consequential actions requiring signed human confirmation


class SeverityLevel(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class QuietHours:
    enabled: bool = False
    start_time: str = "22:00"  # HH:MM
    end_time: str = "07:00"    # HH:MM
    timezone: str = "Asia/Kathmandu"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "timezone": self.timezone,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> QuietHours:
        return cls(
            enabled=data.get("enabled", False),
            start_time=data.get("start_time", "22:00"),
            end_time=data.get("end_time", "07:00"),
            timezone=data.get("timezone", "Asia/Kathmandu"),
        )


@dataclass
class TaskTemplate:
    goal: str
    execution_mode: str = "SINGLE_AGENT_FAST_PATH"  # SINGLE_AGENT_FAST_PATH | FLAT_MULTI_AGENT | HIERARCHICAL_TEAM | ADAPTIVE
    permission_tier: PermissionTier = PermissionTier.TIER_A
    budget_tokens: int = 100000
    budget_paisa: int = 25000  # 250 NPR
    budget_tool_calls: int = 20
    allowed_tools: List[str] = field(default_factory=list)
    allowed_domains: List[str] = field(default_factory=list)
    repo_whitelist: List[str] = field(default_factory=list)
    ancestry: str = "autopilot"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "execution_mode": self.execution_mode,
            "permission_tier": self.permission_tier.value if isinstance(self.permission_tier, PermissionTier) else self.permission_tier,
            "budget_tokens": self.budget_tokens,
            "budget_paisa": self.budget_paisa,
            "budget_tool_calls": self.budget_tool_calls,
            "allowed_tools": self.allowed_tools,
            "allowed_domains": self.allowed_domains,
            "repo_whitelist": self.repo_whitelist,
            "ancestry": self.ancestry,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TaskTemplate:
        tier_str = data.get("permission_tier", "TIER_A")
        try:
            tier = PermissionTier(tier_str)
        except Exception:
            tier = PermissionTier.TIER_A
        return cls(
            goal=data.get("goal", ""),
            execution_mode=data.get("execution_mode", "SINGLE_AGENT_FAST_PATH"),
            permission_tier=tier,
            budget_tokens=data.get("budget_tokens", 100000),
            budget_paisa=data.get("budget_paisa", 25000),
            budget_tool_calls=data.get("budget_tool_calls", 20),
            allowed_tools=data.get("allowed_tools", []),
            allowed_domains=data.get("allowed_domains", []),
            repo_whitelist=data.get("repo_whitelist", []),
            ancestry=data.get("ancestry", "autopilot"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class Schedule:
    schedule_id: str
    tenant_id: str
    owner_user_id: str
    name: str
    description: str
    schedule_type: ScheduleType
    task_template: TaskTemplate
    cron_expr: Optional[str] = None
    interval_seconds: Optional[int] = None
    timezone: str = "Asia/Kathmandu"
    start_time_utc: float = field(default_factory=time.time)
    end_time_utc: Optional[float] = None
    is_paused: bool = False
    max_runs: Optional[int] = None
    run_count: int = 0
    misfire_policy: MisfirePolicy = MisfirePolicy.COALESCE
    idempotency_key: Optional[str] = None
    created_at_utc: float = field(default_factory=time.time)
    updated_at_utc: float = field(default_factory=time.time)
    next_fire_time_utc: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schedule_id": self.schedule_id,
            "tenant_id": self.tenant_id,
            "owner_user_id": self.owner_user_id,
            "name": self.name,
            "description": self.description,
            "schedule_type": self.schedule_type.value if isinstance(self.schedule_type, ScheduleType) else self.schedule_type,
            "task_template": self.task_template.to_dict(),
            "cron_expr": self.cron_expr,
            "interval_seconds": self.interval_seconds,
            "timezone": self.timezone,
            "start_time_utc": self.start_time_utc,
            "end_time_utc": self.end_time_utc,
            "is_paused": self.is_paused,
            "max_runs": self.max_runs,
            "run_count": self.run_count,
            "misfire_policy": self.misfire_policy.value if isinstance(self.misfire_policy, MisfirePolicy) else self.misfire_policy,
            "idempotency_key": self.idempotency_key,
            "created_at_utc": self.created_at_utc,
            "updated_at_utc": self.updated_at_utc,
            "next_fire_time_utc": self.next_fire_time_utc,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Schedule:
        stype = ScheduleType(data.get("schedule_type", "ONE_SHOT"))
        mpolicy = MisfirePolicy(data.get("misfire_policy", "COALESCE"))
        template = TaskTemplate.from_dict(data.get("task_template", {}))
        return cls(
            schedule_id=data["schedule_id"],
            tenant_id=data["tenant_id"],
            owner_user_id=data["owner_user_id"],
            name=data["name"],
            description=data.get("description", ""),
            schedule_type=stype,
            task_template=template,
            cron_expr=data.get("cron_expr"),
            interval_seconds=data.get("interval_seconds"),
            timezone=data.get("timezone", "Asia/Kathmandu"),
            start_time_utc=data.get("start_time_utc", time.time()),
            end_time_utc=data.get("end_time_utc"),
            is_paused=data.get("is_paused", False),
            max_runs=data.get("max_runs"),
            run_count=data.get("run_count", 0),
            misfire_policy=mpolicy,
            idempotency_key=data.get("idempotency_key"),
            created_at_utc=data.get("created_at_utc", time.time()),
            updated_at_utc=data.get("updated_at_utc", time.time()),
            next_fire_time_utc=data.get("next_fire_time_utc"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class JobAttempt:
    attempt_id: str
    job_id: str
    attempt_number: int
    worker_id: str
    started_at_utc: float
    ended_at_utc: Optional[float] = None
    status: JobStatus = JobStatus.RUNNING
    error_details: Optional[str] = None
    exit_code: Optional[int] = None
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attempt_id": self.attempt_id,
            "job_id": self.job_id,
            "attempt_number": self.attempt_number,
            "worker_id": self.worker_id,
            "started_at_utc": self.started_at_utc,
            "ended_at_utc": self.ended_at_utc,
            "status": self.status.value if isinstance(self.status, JobStatus) else self.status,
            "error_details": self.error_details,
            "exit_code": self.exit_code,
            "diagnostics": self.diagnostics,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> JobAttempt:
        return cls(
            attempt_id=data["attempt_id"],
            job_id=data["job_id"],
            attempt_number=data["attempt_number"],
            worker_id=data["worker_id"],
            started_at_utc=data["started_at_utc"],
            ended_at_utc=data.get("ended_at_utc"),
            status=JobStatus(data.get("status", "RUNNING")),
            error_details=data.get("error_details"),
            exit_code=data.get("exit_code"),
            diagnostics=data.get("diagnostics", {}),
        )


@dataclass
class Job:
    job_id: str
    schedule_id: Optional[str]
    tenant_id: str
    owner_user_id: str
    task_id: str
    status: JobStatus = JobStatus.CREATED
    attempt_count: int = 0
    max_attempts: int = 3
    current_lease_owner: Optional[str] = None
    lease_expires_at_utc: Optional[float] = None
    fencing_token: int = 0
    last_heartbeat_at_utc: Optional[float] = None
    scheduled_for_utc: float = field(default_factory=time.time)
    started_at_utc: Optional[float] = None
    completed_at_utc: Optional[float] = None
    error_message: Optional[str] = None
    idempotency_key: Optional[str] = None
    ancestry: str = "autopilot"
    budget_tokens: int = 100000
    consumed_tokens: int = 0
    budget_paisa: int = 25000
    consumed_paisa: int = 0
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    trace_id: str = field(default_factory=lambda: f"trc-{uuid.uuid4().hex[:12]}")
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "schedule_id": self.schedule_id,
            "tenant_id": self.tenant_id,
            "owner_user_id": self.owner_user_id,
            "task_id": self.task_id,
            "status": self.status.value if isinstance(self.status, JobStatus) else self.status,
            "attempt_count": self.attempt_count,
            "max_attempts": self.max_attempts,
            "current_lease_owner": self.current_lease_owner,
            "lease_expires_at_utc": self.lease_expires_at_utc,
            "fencing_token": self.fencing_token,
            "last_heartbeat_at_utc": self.last_heartbeat_at_utc,
            "scheduled_for_utc": self.scheduled_for_utc,
            "started_at_utc": self.started_at_utc,
            "completed_at_utc": self.completed_at_utc,
            "error_message": self.error_message,
            "idempotency_key": self.idempotency_key,
            "ancestry": self.ancestry,
            "budget_tokens": self.budget_tokens,
            "consumed_tokens": self.consumed_tokens,
            "budget_paisa": self.budget_paisa,
            "consumed_paisa": self.consumed_paisa,
            "artifacts": self.artifacts,
            "trace_id": self.trace_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Job:
        return cls(
            job_id=data["job_id"],
            schedule_id=data.get("schedule_id"),
            tenant_id=data["tenant_id"],
            owner_user_id=data["owner_user_id"],
            task_id=data["task_id"],
            status=JobStatus(data.get("status", "CREATED")),
            attempt_count=data.get("attempt_count", 0),
            max_attempts=data.get("max_attempts", 3),
            current_lease_owner=data.get("current_lease_owner"),
            lease_expires_at_utc=data.get("lease_expires_at_utc"),
            fencing_token=data.get("fencing_token", 0),
            last_heartbeat_at_utc=data.get("last_heartbeat_at_utc"),
            scheduled_for_utc=data.get("scheduled_for_utc", time.time()),
            started_at_utc=data.get("started_at_utc"),
            completed_at_utc=data.get("completed_at_utc"),
            error_message=data.get("error_message"),
            idempotency_key=data.get("idempotency_key"),
            ancestry=data.get("ancestry", "autopilot"),
            budget_tokens=data.get("budget_tokens", 100000),
            consumed_tokens=data.get("consumed_tokens", 0),
            budget_paisa=data.get("budget_paisa", 25000),
            consumed_paisa=data.get("consumed_paisa", 0),
            artifacts=data.get("artifacts", []),
            trace_id=data.get("trace_id", f"trc-{uuid.uuid4().hex[:12]}"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class Lease:
    lease_id: str
    job_id: str
    worker_id: str
    fencing_token: int
    acquired_at_utc: float
    expires_at_utc: float
    renewed_at_utc: float


@dataclass
class PermissionGrant:
    grant_id: str
    tenant_id: str
    owner_user_id: str
    tier: PermissionTier
    allowed_tools: List[str]
    allowed_domains: List[str] = field(default_factory=list)
    repo_whitelist: List[str] = field(default_factory=list)
    max_budget_paisa: int = 50000
    expires_at_utc: Optional[float] = None
    is_revoked: bool = False
    created_at_utc: float = field(default_factory=time.time)


@dataclass
class Notification:
    notification_id: str
    tenant_id: str
    user_id: str
    event_type: str  # job.started | job.progress | job.waiting_approval | job.completed | job.failed | budget.exceeded | security.blocked
    title: str
    message: str
    job_id: Optional[str] = None
    schedule_id: Optional[str] = None
    severity: SeverityLevel = SeverityLevel.INFO
    is_read: bool = False
    created_at_utc: float = field(default_factory=time.time)
    idempotency_key: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "notification_id": self.notification_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "event_type": self.event_type,
            "title": self.title,
            "message": self.message,
            "job_id": self.job_id,
            "schedule_id": self.schedule_id,
            "severity": self.severity.value if isinstance(self.severity, SeverityLevel) else self.severity,
            "is_read": self.is_read,
            "created_at_utc": self.created_at_utc,
            "idempotency_key": self.idempotency_key,
            "metadata": self.metadata,
        }


@dataclass
class AutopilotEvent:
    event_id: str
    sequence: int
    tenant_id: str
    job_id: Optional[str]
    schedule_id: Optional[str]
    event_type: str
    payload: Dict[str, Any]
    trace_id: str
    timestamp_utc: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "sequence": self.sequence,
            "tenant_id": self.tenant_id,
            "job_id": self.job_id,
            "schedule_id": self.schedule_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "trace_id": self.trace_id,
            "timestamp_utc": self.timestamp_utc,
        }
