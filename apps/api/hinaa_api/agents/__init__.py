"""
HINAA OS — Phase 11 Autonomous Swarms & Phase 12 Hierarchical Teams Package
Exports authoritative contracts, specialist registry, dispatcher, verifier,
budget controller, event journal, policy bridge, hierarchical planner & supervisor,
and unified orchestration service.
"""

from .contracts import (
    AgentRole,
    AgentSpec,
    ApprovalRecord,
    BudgetLedger,
    CapabilityGrant,
    DelegationRequest,
    ExecutionMode,
    PermissionTier,
    TaskEvent,
    TaskNode,
    TaskResult,
    TaskSpec,
    TaskStatus,
    TeamResult,
    TeamSpec,
    TeamType,
    ToolReceipt,
)
from .registry import SpecialistRegistry
from .budget import BudgetController
from .policy_bridge import PolicyBridge, policy_bridge
from .event_log import EventLogStore
from .planner import TaskPlanner, DAGCycleError
from .hierarchy_planner import HierarchicalPlanner
from .handoff import ContextHandoffManager, ContextScrubber
from .verifier import IndependentVerifier, VerificationResult
from .resume import TaskStore
from .dispatcher import TaskDispatcher
from .supervisor import SupervisorAgent
from .hierarchy_supervisor import HierarchicalSupervisor
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
    "DelegationRequest",
    "ExecutionMode",
    "PermissionTier",
    "TaskEvent",
    "TaskNode",
    "TaskResult",
    "TaskSpec",
    "TaskStatus",
    "TeamResult",
    "TeamSpec",
    "TeamType",
    "ToolReceipt",
    "SpecialistRegistry",
    "BudgetController",
    "PolicyBridge",
    "policy_bridge",
    "EventLogStore",
    "TaskPlanner",
    "HierarchicalPlanner",
    "DAGCycleError",
    "ContextHandoffManager",
    "ContextScrubber",
    "IndependentVerifier",
    "VerificationResult",
    "TaskStore",
    "TaskDispatcher",
    "SupervisorAgent",
    "HierarchicalSupervisor",
    "AgentReflector",
    "AgentOrchestrationService",
    "agent_service",
    "worker_hive",
]
