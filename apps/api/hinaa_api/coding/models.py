"""Data models, task specifications, and activity event contracts for the Coding Agent."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field

from hinaa_api.sandbox.isolation_base import IsolationBackendType


class CodingTaskState(str, Enum):
    CREATED = "CREATED"
    INITIALIZING = "INITIALIZING"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    TESTING = "TESTING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"


class CodingActionType(str, Enum):
    INSPECT_WORKSPACE = "INSPECT_WORKSPACE"
    SEARCH_SYMBOLS = "SEARCH_SYMBOLS"
    READ_FILE = "READ_FILE"
    APPLY_PATCH = "APPLY_PATCH"
    RUN_TEST = "RUN_TEST"
    RUN_LINT = "RUN_LINT"
    RUN_BUILD = "RUN_BUILD"
    RUN_COMMAND = "RUN_COMMAND"
    GIT_STATUS = "GIT_STATUS"
    GIT_BRANCH = "GIT_BRANCH"
    GIT_COMMIT = "GIT_COMMIT"
    GIT_PUSH = "GIT_PUSH"          # Tier C
    DEPLOY = "DEPLOY"              # Tier C
    ROLLBACK = "ROLLBACK"


class CodingPermissionTier(str, Enum):
    TIER_A_READ_ONLY = "TIER_A_READ_ONLY"
    TIER_B_SCOPED_MUTATION = "TIER_B_SCOPED_MUTATION"
    TIER_C_SPECIFIC_APPROVAL = "TIER_C_SPECIFIC_APPROVAL"


class CodingActionRequest(BaseModel):
    action_id: str = Field(default_factory=lambda: f"act-{uuid4().hex[:8]}")
    task_id: str
    action_type: CodingActionType
    target_file: Optional[str] = None
    target_content: Optional[str] = None
    replacement_content: Optional[str] = None
    command_args: Optional[List[str]] = None
    user_approved: bool = False
    approval_token: Optional[str] = None


class CodingStepResult(BaseModel):
    step_id: str
    action_type: CodingActionType
    status: str  # "SUCCESS", "FAILED", "APPROVAL_REQUIRED", "CANCELLED"
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    diff: str = ""
    duration_ms: float = 0.0
    error: Optional[str] = None


class CodingTaskEvent(BaseModel):
    """Activity event emitted over SSE for real-time frontend observation."""

    run_id: str
    event_id: str = Field(default_factory=lambda: f"evt-{uuid4().hex[:8]}")
    type: str  # run.started, model.selecting, model.selected, tool.started, tool.completed, tool.failed, artifact.ready, run.completed, run.failed
    label: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    extra: Dict[str, Any] = Field(default_factory=dict)


class CodingTaskSpec(BaseModel):
    task_id: str = Field(default_factory=lambda: f"task-code-{uuid4().hex[:8]}")
    user_id: str = "default_user"
    tenant_id: str = "default_tenant"
    workspace_path: str
    objective: str
    max_repair_iterations: int = Field(default=3, ge=1, le=10)
    timeout_seconds: float = Field(default=120.0, ge=10.0, le=600.0)
    require_high_security: bool = False
    create_pr: bool = False
    repo: Optional[str] = None
    base_branch: Optional[str] = "main"
    task_type: str = "feat"
    approval_token: Optional[str] = None


class CodingTaskStatus(BaseModel):
    task_id: str
    user_id: str
    tenant_id: str
    state: CodingTaskState
    workspace_path: str
    objective: str
    current_iteration: int = 0
    max_repair_iterations: int = 3
    backend_type: IsolationBackendType = IsolationBackendType.RESTRICTED_HOST_PROCESS
    files_changed: List[str] = Field(default_factory=list)
    step_results: List[CodingStepResult] = Field(default_factory=list)
    diff_summary: str = ""
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    commit_sha: Optional[str] = None
    branch_name: Optional[str] = None
    pr_url: Optional[str] = None
    pr_number: Optional[int] = None
    verification_evidence: List[str] = Field(default_factory=list)
