"""HINAA OS Browser Automation & Web Operations Module (Phase 07).

Provides robust, permission-tiered, SSRF-defended, and isolated browser capabilities
for autonomous research, verified task execution, and UI evidence streaming.
"""

from .action_schema import (
    ActionPostcondition,
    ActionTarget,
    BrowserActionRequest,
    BrowserActionResult,
    BrowserActionType,
    BrowserTaskApprovalRequest,
    BrowserTaskEvent,
    BrowserTaskSpec,
    BrowserTaskState,
    PermissionTier,
    TabInfo,
)
from .evidence import EvidenceCollector
from .executor import ActionExecutor
from .extraction import PageExtractor
from .file_transfer import FileTransferManager
from .navigation import NavigationHandler
from .planner import BrowserTaskPlanner
from .policy import BrowserSecurityPolicy
from .recovery import RecoveryHandler
from .runtime import BrowserRuntimeManager
from .service import BrowserAutomationService
from .session_manager import BrowserSession, BrowserSessionManager

__all__ = [
    "ActionPostcondition",
    "ActionTarget",
    "BrowserActionRequest",
    "BrowserActionResult",
    "BrowserActionType",
    "BrowserAutomationService",
    "BrowserRuntimeManager",
    "BrowserSecurityPolicy",
    "BrowserSession",
    "BrowserSessionManager",
    "BrowserTaskApprovalRequest",
    "BrowserTaskEvent",
    "BrowserTaskPlanner",
    "BrowserTaskSpec",
    "BrowserTaskState",
    "EvidenceCollector",
    "ActionExecutor",
    "PageExtractor",
    "FileTransferManager",
    "NavigationHandler",
    "PermissionTier",
    "RecoveryHandler",
    "TabInfo",
]
