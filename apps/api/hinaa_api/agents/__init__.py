"""
HINAA OS — Phase 11 Autonomous Tooling & Multi-Agent Swarms Package
Exports authoritative contracts, specialist registry, dispatcher, verifier,
budget controller, event journal, policy bridge, supervisor, and unified service.
"""

from .contracts import (
    AgentRole,
    AgentSpec,
    ApprovalRecord,
    BudgetLedger,
    CapabilityGrant,
    PermissionTier,
    TaskEvent,
    TaskNode,
    TaskResult,
    TaskSpec,
    TaskStatus,
    ToolReceipt,
)
from .registry import SpecialistRegistry
from .budget import BudgetController
from .policy_bridge import PolicyBridge, policy_bridge
from .event_log import EventLogStore
from .planner import TaskPlanner, DAGCycleError
from .handoff import ContextHandoffManager, ContextScrubber
from .verifier import IndependentVerifier, VerificationResult
from .resume import TaskStore
from .dispatcher import TaskDispatcher
from .supervisor import SupervisorAgent
from .reflection import AgentReflector
from .service import AgentOrchestrationService, agent_service

# Re-export legacy worker_hive for route compatibility
try:
    from .worker_hive import worker_hive
except ImportError:
    worker_hive = None

__all__ = [
    "AgentRole",
    "AgentSpec",
    "ApprovalRecord",
    "BudgetLedger",
    "CapabilityGrant",
    "PermissionTier",
    "TaskEvent",
    "TaskNode",
    "TaskResult",
    "TaskSpec",
    "TaskStatus",
    "ToolReceipt",
    "SpecialistRegistry",
    "BudgetController",
    "PolicyBridge",
    "policy_bridge",
    "EventLogStore",
    "TaskPlanner",
    "DAGCycleError",
    "ContextHandoffManager",
    "ContextScrubber",
    "IndependentVerifier",
    "VerificationResult",
    "TaskStore",
    "TaskDispatcher",
    "SupervisorAgent",
    "AgentReflector",
    "AgentOrchestrationService",
    "agent_service",
    "worker_hive",
]
