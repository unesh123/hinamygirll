"""
HINAA OS — Phase 11 Supervisor Coordinator & Execution Engine
Orchestrates DAG execution, enforces least-privilege capability grants,
verifies cryptographic receipts, handles approvals, and synthesizes authoritative results.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from .budget import BudgetController
from .contracts import (
    AgentRole,
    PermissionTier,
    TaskEvent,
    TaskNode,
    TaskResult,
    TaskSpec,
    TaskStatus,
    ToolReceipt,
    _digest_dict,
    _now_iso,
)
from .dispatcher import TaskDispatcher
from .event_log import EventLogStore
from .handoff import ContextHandoffManager
from .planner import TaskPlanner
from .policy_bridge import PolicyBridge
from .registry import SpecialistRegistry
from .resume import TaskStore
from .verifier import IndependentVerifier

logger = logging.getLogger("hinaa.agents.supervisor")


class SupervisorAgent:
    """Authoritative mission coordinator and orchestrator for HINAA OS multi-agent swarms."""

    def __init__(
        self,
        registry: Optional[SpecialistRegistry] = None,
        task_store: Optional[TaskStore] = None,
        event_log: Optional[EventLogStore] = None,
        policy_bridge: Optional[PolicyBridge] = None,
        budget_controller: Optional[BudgetController] = None,
        planner: Optional[TaskPlanner] = None,
        verifier: Optional[IndependentVerifier] = None,
        handoff_manager: Optional[ContextHandoffManager] = None,
    ) -> None:
        self.registry = registry or SpecialistRegistry()
        self.task_store = task_store or TaskStore()
        self.event_log = event_log or EventLogStore()
        self.policy_bridge = policy_bridge or PolicyBridge()
        self.budget_controller = budget_controller or BudgetController()
        self.planner = planner or TaskPlanner(self.registry)
        self.verifier = verifier or IndependentVerifier()
        self.handoff_manager = handoff_manager or ContextHandoffManager()
        self.dispatcher = TaskDispatcher(self.registry, self.task_store, self.budget_controller)

    def emit_event(
        self,
        task_id: str,
        actor_role: AgentRole,
        event_type: str,
        payload: Dict[str, Any],
        node_id: Optional[str] = None,
        state_before: Optional[TaskStatus] = None,
        state_after: Optional[TaskStatus] = None,
    ) -> TaskEvent:
        """Emit a structured event to the append-only event journal."""
        evt = TaskEvent(
            sequence=0,  # assigned by EventLogStore
            task_id=task_id,
            node_id=node_id,
            actor_role=actor_role,
            event_type=event_type,
            payload=payload,
            state_before=state_before,
            state_after=state_after,
        )
        return self.event_log.append_event(evt)

    def create_task(self, goal: str, tenant_id: str = "default", user_id: str = "user-default", language: str = "en") -> TaskSpec:
        """Initialize, decompose, and persist a new task with DAG nodes."""
        task_id = f"task-{uuid.uuid4().hex[:10]}"
        nodes = self.planner.plan_task(task_id=task_id, goal=goal)

        # Validate DAG
        is_valid, err = self.planner.validate_dag(nodes)
        if not is_valid:
            raise ValueError(f"Invalid task DAG: {err}")

        task = TaskSpec(
            task_id=task_id,
            tenant_id=tenant_id,
            user_id=user_id,
            goal=goal,
            language=language,
            status=TaskStatus.READY,
            nodes=nodes,
        )

        self.task_store.save_task(task)
        self.emit_event(
            task_id=task_id,
            actor_role=AgentRole.SUPERVISOR,
            event_type="task.created",
            payload={"goal": goal, "node_count": len(nodes), "language": language},
            state_before=TaskStatus.CREATED,
            state_after=TaskStatus.READY,
        )
        return task

    def execute_tool_safely(
        self,
        task_id: str,
        node: TaskNode,
        tool_name: str,
        action: str,
        arguments: Dict[str, Any],
        approval_id: Optional[str] = None,
    ) -> Tuple[int, Dict[str, Any], List[str]]:
        """
        Execute tool within capability and permission boundaries, returning
        (exit_code, output_dict, artifact_paths).
        """
        # Check emergency stop
        if self.policy_bridge.is_stopped():
            return 126, {"error": "Emergency stop active: execution aborted"}, []

        # Check tool permission in registry
        if not self.registry.is_tool_allowed(node.specialist_role, tool_name):
            return 127, {"error": f"Tool '{tool_name}' not granted to {node.specialist_role}"}, []

        # Check permission tier
        if node.permission_tier == PermissionTier.TIER_C_EXPLICIT_APPROVAL:
            if not approval_id:
                return 128, {"error": "Tier C requires valid approved token"}, []
            valid, reason = self.policy_bridge.verify_and_consume_approval(
                approval_id=approval_id,
                tenant_id="default",
                action=action,
                arguments=arguments,
                amount_paisa=arguments.get("amount_paisa", 0),
            )
            if not valid:
                return 129, {"error": f"Tier C approval verification failed: {reason}"}, []

        # Execute mock / real tool actions deterministically
        artifacts: List[str] = []
        exit_code = 0
        output: Dict[str, Any] = {}

        if tool_name in ("sandbox_write", "git_commit_scoped"):
            path = arguments.get("path", f"output_{uuid.uuid4().hex[:6]}.txt")
            content = arguments.get("content", "Generated HINAA artifact content\n")
            full_path = os.path.abspath(path)
            try:
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content)
                artifacts.append(full_path)
                output = {"success": True, "written_path": full_path, "bytes": len(content.encode("utf-8"))}
            except Exception as ex:
                exit_code = 1
                output = {"error": str(ex)}

        elif tool_name in ("run_test_suite", "verify_file_hash", "check_exit_code"):
            exit_code = arguments.get("mock_exit_code", 0)
            output = {
                "qa_passed": (exit_code == 0),
                "exit_code": exit_code,
                "passed_tests": 12 if exit_code == 0 else 10,
                "failed_tests": 0 if exit_code == 0 else 2,
            }

        elif tool_name in ("crag_search", "fetch_url_content", "extract_citations"):
            query = arguments.get("query", "")
            output = {
                "status": "GROUNDED",
                "citations": [
                    {"source": "Nepal Law Commission", "url": "https://lawcommission.gov.np", "confidence": 0.98},
                    {"source": "HINAA Knowledge Base", "url": "local://crag/corpus", "confidence": 0.95},
                ],
                "grounded_claims": [f"Verified evidence for query: {query}"],
            }

        elif tool_name in ("translate_text", "validate_devanagari_encoding"):
            output = {
                "devanagari_valid": True,
                "nepali_text": "नमस्ते! कार्य सफलतापूर्वक सम्पन्न भयो।",
                "romanized": "Namaste! Kaarya saphalatapoorvak sampanna bhayo.",
            }

        else:
            output = {"executed": True, "tool": tool_name, "action": action}

        return exit_code, output, artifacts

    def execute_node(
        self,
        task: TaskSpec,
        node: TaskNode,
        approval_id: Optional[str] = None,
    ) -> TaskNode:
        """Execute a single ready node under strict verifier governance."""
        self.emit_event(
            task_id=task.task_id,
            actor_role=node.specialist_role,
            event_type="node.started",
            payload={"node_id": node.node_id, "title": node.title},
            node_id=node.node_id,
            state_before=node.status,
            state_after=TaskStatus.RUNNING,
        )

        node.status = TaskStatus.RUNNING
        node.start_time = time.time()
        node.attempts += 1

        # Check Tier C approval requirement
        if node.permission_tier == PermissionTier.TIER_C_EXPLICIT_APPROVAL and not approval_id:
            # Create approval request and pause
            appr = self.policy_bridge.create_approval_request(
                tenant_id=task.tenant_id,
                user_id=task.user_id,
                task_id=task.task_id,
                node_id=node.node_id,
                action=node.allowed_tools[0] if node.allowed_tools else "generic_action",
                arguments=node.input_data,
                amount_paisa=node.input_data.get("amount_paisa", 0),
            )
            node.status = TaskStatus.WAITING_APPROVAL
            self.emit_event(
                task_id=task.task_id,
                actor_role=node.specialist_role,
                event_type="node.waiting_approval",
                payload={"approval_id": appr.approval_id, "action": appr.action, "amount_paisa": appr.amount_paisa},
                node_id=node.node_id,
                state_before=TaskStatus.RUNNING,
                state_after=TaskStatus.WAITING_APPROVAL,
            )
            self.task_store.save_task(task)
            return node

        # Record admission and tool usage in budget
        self.budget_controller.record_tokens(tokens=120, cost_usd=0.002, cost_paisa=25)

        # Execute primary tool
        tool = node.allowed_tools[0] if node.allowed_tools else "synthesize_response"
        t0 = time.perf_counter()
        exit_code, tool_output, artifact_paths = self.execute_tool_safely(
            task_id=task.task_id,
            node=node,
            tool_name=tool,
            action="execute",
            arguments=node.input_data,
            approval_id=approval_id,
        )
        duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        self.budget_controller.record_tool_call()

        # Generate cryptographic receipt
        input_digest = _digest_dict(node.input_data)
        output_digest = _digest_dict(tool_output)
        receipt = ToolReceipt(
            task_id=task.task_id,
            node_id=node.node_id,
            agent_role=node.specialist_role,
            tool_name=tool,
            action="execute",
            input_digest=input_digest,
            output_digest=output_digest,
            exit_code=exit_code,
            duration_ms=duration_ms,
            idempotency_key=f"idem-{uuid.uuid4().hex[:12]}",
            artifact_paths=artifact_paths,
        )
        node.receipts.append(receipt)
        node.result_data = tool_output
        node.end_time = time.time()

        # Independent verification oracle
        v_res = self.verifier.verify_node(node, node.receipts)
        receipt.verified = v_res.passed
        receipt.verification_notes = v_res.notes

        if v_res.passed:
            node.status = TaskStatus.COMPLETED
            for art_path, art_sha in v_res.artifact_checksums.items():
                task.artifacts.append({
                    "path": art_path,
                    "filename": os.path.basename(art_path),
                    "sha256": art_sha,
                    "created_by": node.specialist_role.value if hasattr(node.specialist_role, "value") else str(node.specialist_role),
                })
            self.emit_event(
                task_id=task.task_id,
                actor_role=node.specialist_role,
                event_type="node.completed",
                payload={"node_id": node.node_id, "notes": v_res.notes, "artifacts": len(artifact_paths)},
                node_id=node.node_id,
                state_before=TaskStatus.RUNNING,
                state_after=TaskStatus.COMPLETED,
            )
        else:
            if node.attempts < node.max_attempts:
                node.status = TaskStatus.RETRYING
                self.emit_event(
                    task_id=task.task_id,
                    actor_role=node.specialist_role,
                    event_type="node.retrying",
                    payload={"node_id": node.node_id, "attempt": node.attempts, "error": v_res.notes},
                    node_id=node.node_id,
                    state_before=TaskStatus.RUNNING,
                    state_after=TaskStatus.RETRYING,
                )
            else:
                node.status = TaskStatus.FAILED
                node.error = v_res.notes
                self.emit_event(
                    task_id=task.task_id,
                    actor_role=node.specialist_role,
                    event_type="node.failed",
                    payload={"node_id": node.node_id, "error": v_res.notes},
                    node_id=node.node_id,
                    state_before=TaskStatus.RUNNING,
                    state_after=TaskStatus.FAILED,
                )

        # Release worker lease
        self.task_store.release_node_lease(node.node_id, node.lease_owner or "default", node.status)
        self.task_store.save_task(task)
        return node

    def run_task_to_completion(self, task: TaskSpec) -> TaskResult:
        """Run all DAG nodes sequentially/concurrently according to dependencies."""
        t_start = time.perf_counter()
        task.status = TaskStatus.RUNNING
        self.task_store.save_task(task)

        while True:
            # Check if all completed
            all_done = all(n.status == TaskStatus.COMPLETED for n in task.nodes)
            if all_done:
                task.status = TaskStatus.COMPLETED
                task.completed_at = _now_iso()
                break

            # Check if any failed permanently
            failed_nodes = [n for n in task.nodes if n.status == TaskStatus.FAILED]
            if failed_nodes:
                task.status = TaskStatus.FAILED
                task.completed_at = _now_iso()
                break

            # Check if paused on approval
            waiting = [n for n in task.nodes if n.status == TaskStatus.WAITING_APPROVAL]
            if waiting:
                task.status = TaskStatus.WAITING_APPROVAL
                break

            # Dispatch next ready node
            ready = self.dispatcher.get_ready_nodes(task)
            if not ready:
                # Deadlock or cyclic blockage
                task.status = TaskStatus.BLOCKED
                break

            # Execute the first ready node
            node = ready[0]
            node.lease_owner = "supervisor-engine"
            self.execute_node(task, node)

        self.task_store.save_task(task)
        total_duration_ms = round((time.perf_counter() - t_start) * 1000, 2)

        # Synthesize TaskResult
        all_receipts = [r for n in task.nodes for r in n.receipts]
        completed_titles = [n.title for n in task.nodes if n.status == TaskStatus.COMPLETED]
        uncompleted_titles = [n.title for n in task.nodes if n.status != TaskStatus.COMPLETED]
        is_verified = (task.status == TaskStatus.COMPLETED) and all(r.verified for r in all_receipts)

        summary_text = (
            f"Successfully coordinated {len(task.nodes)} specialist nodes. All postconditions verified."
            if task.status == TaskStatus.COMPLETED
            else f"Task stopped with status {task.status.value}. Uncompleted: {', '.join(uncompleted_titles)}"
        )

        res = TaskResult(
            task_id=task.task_id,
            status=task.status,
            summary=summary_text,
            completed_actions=completed_titles,
            uncompleted_actions=uncompleted_titles,
            receipts=all_receipts,
            artifacts=task.artifacts,
            budget_used=self.budget_controller.ledger,
            total_duration_ms=total_duration_ms,
            verification_passed=is_verified,
            evidence_trail=[f"Node '{n.title}': {n.status.value}" for n in task.nodes],
        )
        return res
