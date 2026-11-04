"""Typed schemas and data models for HINAA OS Browser Automation & Web Operations.

Defines all browser actions, parameters, postconditions, evidence models,
and lifecycle states used across execution, planning, and UI streaming.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BrowserTaskState(str, Enum):
    """Task lifecycle state machine states."""
    CREATED = "CREATED"
    AUTHORIZATION_CHECK = "AUTHORIZATION_CHECK"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    RETRYING = "RETRYING"
    CANCELLING = "CANCELLING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PermissionTier(str, Enum):
    """Tiered security and approval model."""
    TIER_A_READ_ONLY = "TIER_A_READ_ONLY"         # Inspect, read, screenshot, extract
    TIER_B_SCOPED_EXECUTION = "TIER_B_SCOPED_EXECUTION" # Form fills on test sandbox, downloads
    TIER_C_SPECIFIC_APPROVAL = "TIER_C_SPECIFIC_APPROVAL" # External mutation, submit, delete, buy


class BrowserActionType(str, Enum):
    """Canonical typed browser tools."""
    OPEN = "browser.open"
    INSPECT = "browser.inspect"
    FIND = "browser.find"
    CLICK = "browser.click"
    FILL = "browser.fill"
    SELECT = "browser.select"
    CHECK = "browser.check"
    SCROLL = "browser.scroll"
    WAIT_FOR = "browser.wait_for"
    SCREENSHOT = "browser.screenshot"
    EXTRACT_TABLE = "browser.extract_table"
    DOWNLOAD = "browser.download"
    UPLOAD_APPROVED = "browser.upload_approved"
    SWITCH_TAB = "browser.switch_tab"
    CLOSE = "browser.close"
    CANCEL = "browser.cancel"


class ActionTarget(BaseModel):
    """Target element locator specification."""
    by: Literal["role", "text", "label", "placeholder", "css", "test_id", "coordinate"] = "role"
    selector: str = ""
    role: Optional[str] = None
    name: Optional[str] = None
    exact: bool = False
    index: int = 0
    coordinates: Optional[tuple[int, int]] = None  # (x, y) fallback if specified


class ActionPostcondition(BaseModel):
    """Verifiable condition to assert after action execution."""
    check_type: Literal[
        "url_contains",
        "url_matches",
        "element_visible",
        "element_hidden",
        "text_present",
        "value_equals",
        "download_completed",
        "none",
    ] = "none"
    expected_value: Optional[str] = None
    timeout_ms: int = 5000


class BrowserActionRequest(BaseModel):
    """Typed request payload for a single browser tool execution."""
    action_id: str
    task_id: str
    action_type: BrowserActionType
    target: Optional[ActionTarget] = None
    value: Optional[str] = None
    url: Optional[str] = None
    tab_id: Optional[str] = None
    timeout_ms: int = 15000
    expected_origin: Optional[str] = None
    postcondition: Optional[ActionPostcondition] = None
    user_approved: bool = False
    approval_token: Optional[str] = None


class BrowserActionResult(BaseModel):
    """Verifiable outcome of an executed browser action."""
    action_id: str
    task_id: str
    action_type: BrowserActionType
    status: Literal["SUCCESS", "FAILED", "APPROVAL_REQUIRED", "CANCELLED", "TIMEOUT"]
    observed_url: str = ""
    observed_title: str = ""
    elapsed_ms: float = 0.0
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None
    postcondition_verified: bool = False
    postcondition_details: Optional[str] = None
    extracted_data: Optional[Any] = None
    screenshot_b64: Optional[str] = None
    screenshot_path: Optional[str] = None
    timestamp: str = Field(default_factory=_utc_now_iso)


class TabInfo(BaseModel):
    """Information regarding an active browser tab."""
    tab_id: str
    url: str
    title: str
    origin: str
    created_at: str = Field(default_factory=_utc_now_iso)
    is_active: bool = False


class BrowserTaskApprovalRequest(BaseModel):
    """Details presented to human when Tier C approval is demanded."""
    approval_id: str
    task_id: str
    action_type: BrowserActionType
    target_origin: str
    destination_url: str
    summary: str
    proposed_payload: Dict[str, Any] = Field(default_factory=dict)
    risk_level: Literal["HIGH", "CRITICAL"] = "HIGH"
    created_at: str = Field(default_factory=_utc_now_iso)


class BrowserTaskEvent(BaseModel):
    """Streamed event payload for UI and telemetry."""
    event_id: str
    task_id: str
    state: BrowserTaskState
    action_type: Optional[BrowserActionType] = None
    message: str
    observed_url: Optional[str] = None
    timestamp: str = Field(default_factory=_utc_now_iso)
    screenshot_path: Optional[str] = None
    approval_request: Optional[BrowserTaskApprovalRequest] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)


class BrowserTaskSpec(BaseModel):
    """High-level specification of a browser automation task."""
    task_id: str
    objective: str
    user_id: str
    tenant_id: str = "default_tenant"
    start_url: Optional[str] = None
    max_steps: int = 15
    max_duration_seconds: int = 120
    max_memory_mb: int = 512
    max_download_bytes: int = 25 * 1024 * 1024  # 25 MB
    allow_tier_c_approvals: bool = True
    trace_id: Optional[str] = None
    created_at: str = Field(default_factory=_utc_now_iso)
