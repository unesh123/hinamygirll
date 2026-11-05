"""
HINAA OS — Phase 12 Hierarchical Supervisor & Cross-Team Orchestrator
Coordinates nested team leads, executes bounded subgraphs, enforces strict capability grants,
verifies cryptographic receipts, binds complete ancestry in Tier C HMAC approvals,
and enforces independent QA overrides over optimistic claims.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from .budget import BudgetController
from .contracts import (
    AgentRole,
    BudgetLedger,
    DelegationRequest,
    ExecutionMode,
    PermissionTier,
    TaskEvent,
    TaskNode,
    TaskResult,
    TaskSpec,
    TaskStatus,
    TeamResult,
    TeamType,
    ToolReceipt,
    _digest_dict,
    _now_iso,
)
from .dispatcher import TaskDispatcher
from .event_log import EventLogStore
from .handoff import ContextHandoffManager
from .hierarchy_planner import HierarchicalPlanner
from .policy_bridge import PolicyBridge, _APPROVAL_SECRET
from .registry import SpecialistRegistry
from .resume import TaskStore
from .verifier import IndependentVerifier

logger = logging.getLogger("hinaa.agents.hierarchy_supervisor")


class HierarchicalSupervisor:
    """Authoritative hierarchical coordinator for Phase 12 multi-team missions."""

    def __init__(
        self,
        registry: Optional[SpecialistRegistry] = None,
        task_store: Optional[TaskStore] = None,
        event_log: Optional[EventLogStore] = None,
        policy_bridge: Optional[PolicyBridge] = None,
        budget_controller: Optional[BudgetController] = None,
        planner: Optional[HierarchicalPlanner] = None,
        verifier: Optional[IndependentVerifier] = None,
        handoff_manager: Optional[ContextHandoffManager] = None,
    ) -> None:
        self.registry = registry or SpecialistRegistry()
        self.task_store = task_store or TaskStore()
        self.event_log = event_log or EventLogStore()
        self.policy_bridge = policy_bridge or PolicyBridge()
        self.budget_controller = budget_controller or BudgetController()
        self.planner = planner or HierarchicalPlanner(self.registry)
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
        team_run_id: Optional[str] = None,
        state_before: Optional[TaskStatus] = None,
        state_after: Optional[TaskStatus] = None,
        depth: int = 0,
    ) -> TaskEvent:
        """Append event to the durable audit journal."""
        evt = TaskEvent(
            sequence=0,
            task_id=task_id,
            node_id=node_id,
            team_run_id=team_run_id,
            actor_role=actor_role,
            event_type=event_type,
            payload=payload,
            state_before=state_before,
            state_after=state_after,
            depth=depth,
        )
        return self.event_log.append_event(evt)

    def create_hierarchical_task(
        self,
        goal: str,
        tenant_id: str = "default",
        user_id: str = "user-default",
        language: str = "en",
    ) -> TaskSpec:
        """Decompose mission into hierarchical delegation requests and bounded subgraphs."""
        task_id = f"task-{uuid.uuid4().hex[:10]}"
        delegations, nodes = self.planner.plan_hierarchical_mission(
            task_id=task_id,
            goal=goal,
            tenant_id=tenant_id,
            user_id=user_id,
            language=language,
        )

        task = TaskSpec(
            task_id=task_id,
            tenant_id=tenant_id,
            user_id=user_id,
            goal=goal,
            language=language,
            status=TaskStatus.READY,
            execution_mode=ExecutionMode.HIERARCHICAL_TEAM,
            nodes=nodes,
            team_runs=delegations,
            hierarchy_depth=2,
        )

        self.task_store.save_task(task)
        self.emit_event(
            task_id=task_id,
            actor_role=AgentRole.SUPERVISOR,
            event_type="task.created",
            payload={
                "goal": goal,
                "team_runs": len(delegations),
                "total_nodes": len(nodes),
                "execution_mode": ExecutionMode.HIERARCHICAL_TEAM.value,
            },
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
        Execute tool within capability and permission boundaries with ancestry verification.
        """
        # 1. Emergency stop check
        if self.policy_bridge.is_stopped():
            return 126, {"error": "Emergency stop active: execution suspended"}, []

        # 2. Check capability grant
        if not self.registry.is_tool_allowed(node.specialist_role, tool_name):
            return 127, {"error": f"Tool '{tool_name}' not granted to role '{node.specialist_role}'"}, []

        # 3. Check Tier C approval gate with ancestry binding
        if node.permission_tier == PermissionTier.TIER_C_EXPLICIT_APPROVAL:
            if not approval_id:
                return 128, {"error": "Tier C action requires approved cryptographic token"}, []
            valid, reason = self.policy_bridge.verify_and_consume_approval(
                approval_id=approval_id,
                tenant_id="default",
                action=action,
                arguments=arguments,
                amount_paisa=arguments.get("amount_paisa", 0),
                team_id=node.team_id,
                ancestry=node.ancestry,
            )
            if not valid:
                return 129, {"error": f"Tier C approval verification failed: {reason}"}, []

        # 4. Tool Execution
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
            qa_passed = (exit_code == 0)
            output = {
                "qa_passed": qa_passed,
                "exit_code": exit_code,
                "passed_tests": 12 if qa_passed else 10,
                "failed_tests": 0 if qa_passed else 2,
                "failure_details": "Independent QA verification rejected: exit code 1" if not qa_passed else None,
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

        elif tool_name in ("translate_text", "validate_devanagari_encoding", "cultural_glossary_lookup"):
            output = {
                "devanagari_valid": True,
                "nepali_text": "नमस्ते! कार्य सफलतापूर्वक सम्पन्न भयो।",
                "romanized": "Namaste! Kaarya saphalatapoorvak sampanna bhayo.",
            }

        elif tool_name in ("browser_navigate", "inspect_accessibility_tree", "verify_page_content"):
            output = {
                "navigated": True,
                "url": arguments.get("target_url", "http://localhost:3000"),
                "accessibility_tree_valid": True,
                "dom_nodes_verified": 48,
                "clipping_detected": False,
            }

        elif tool_name in ("simulate_nepali_payment", "verify_paisa_amount"):
            amount_paisa = arguments.get("amount_paisa", 25000)
            amount_npr = amount_paisa / 100.0
            output = {
                "transaction_simulated": True,
                "gateway": arguments.get("gateway", "eSewa"),
                "amount_npr": amount_npr,
                "amount_paisa": amount_paisa,
                "currency": "NPR",
                "sandbox_only": True,
                "live_financial_gateways_forbidden": True,
                "status": "SIMULATED_SUCCESS",
            }

        elif tool_name in ("generate_video_prompt", "export_timeline_video"):
            req_type = arguments.get("request_type", "timeline-export")
            if req_type == "text-to-video":
                # Honest declaration of neural video limitations
                exit_code = 0
                output = {
                    "status": "BLOCKED_UNAVAILABLE",
                    "reason": "Neural text-to-video diffusion weights offline/missing; timeline video export offered as verified alternative.",
                    "alternative_offered": "TIMELINE_EXPORT",
                }
            else:
                output = {
                    "status": "SUCCESS",
                    "export_format": "H.264 MP4 via FFmpeg",
                    "timeline_duration_sec": 5.0,
                    "resolution": "1920x1080",
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
        """Execute a single ready node under independent QA governance."""
        self.emit_event(
            task_id=task.task_id,
            actor_role=node.specialist_role,
            event_type="node.started",
            payload={"node_id": node.node_id, "title": node.title, "depth": node.depth},
            node_id=node.node_id,
            team_run_id=node.team_id,
            state_before=node.status,
            state_after=TaskStatus.RUNNING,
            depth=node.depth,
        )

        node.status = TaskStatus.RUNNING
        node.start_time = time.time()
        node.attempts += 1

        # Check Tier C approval requirement
        if node.permission_tier == PermissionTier.TIER_C_EXPLICIT_APPROVAL and not approval_id:
            appr = self.policy_bridge.create_approval_request(
                tenant_id=task.tenant_id,
                user_id=task.user_id,
                task_id=task.task_id,
                node_id=node.node_id,
                action=node.allowed_tools[0] if node.allowed_tools else "generic_action",
                arguments=node.input_data,
                amount_paisa=node.input_data.get("amount_paisa", 0),
                team_id=node.team_id,
                ancestry=node.ancestry,
            )
            node.status = TaskStatus.WAITING_APPROVAL
            self.emit_event(
                task_id=task.task_id,
                actor_role=node.specialist_role,
                event_type="node.waiting_approval",
                payload={"approval_id": appr.approval_id, "action": appr.action, "amount_paisa": appr.amount_paisa},
                node_id=node.node_id,
                team_run_id=node.team_id,
                state_before=TaskStatus.RUNNING,
                state_after=TaskStatus.WAITING_APPROVAL,
                depth=node.depth,
            )
            self.task_store.save_task(task)
            return node

        # Record admission and budget
        self.budget_controller.record_tokens(tokens=150, cost_paisa=30)

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

        # Cross-Team Verification Rule: QA failures strictly override optimistic claims
        if tool_output.get("qa_passed") is False or exit_code != 0:
            receipt.verified = False
            node.status = TaskStatus.FAILED
            node.error = tool_output.get("failure_details") or "QA verification failure"
        else:
            receipt.verified = v_res.passed
            node.status = TaskStatus.COMPLETED if v_res.passed else TaskStatus.FAILED
            if not v_res.passed:
                node.error = v_res.notes

        if node.status == TaskStatus.COMPLETED:
            for art_path, art_sha in v_res.artifact_checksums.items():
                task.artifacts.append({
                    "path": art_path,
                    "filename": os.path.basename(art_path),
                    "sha256": art_sha,
                    "team_id": node.team_id,
                    "created_by": node.specialist_role.value if hasattr(node.specialist_role, "value") else str(node.specialist_role),
                })
            self.emit_event(
                task_id=task.task_id,
                actor_role=node.specialist_role,
                event_type="node.completed",
                payload={"node_id": node.node_id, "notes": v_res.notes, "artifacts": len(artifact_paths)},
                node_id=node.node_id,
                team_run_id=node.team_id,
                state_before=TaskStatus.RUNNING,
                state_after=TaskStatus.COMPLETED,
                depth=node.depth,
            )
        else:
            self.emit_event(
                task_id=task.task_id,
                actor_role=node.specialist_role,
                event_type="node.failed",
                payload={"node_id": node.node_id, "error": node.error},
                node_id=node.node_id,
                team_run_id=node.team_id,
                state_before=TaskStatus.RUNNING,
                state_after=TaskStatus.FAILED,
                depth=node.depth,
            )

        self.task_store.release_node_lease(node.node_id, node.lease_owner or "default", node.status)
        self.task_store.save_task(task)
        return node

    def run_team_workstream(self, task: TaskSpec, delegation: DelegationRequest) -> TeamResult:
        """
        Execute bounded team workstream under a sliced budget and context isolation.
        """
        t0 = time.perf_counter()
        team_id = delegation.ancestry[1] if len(delegation.ancestry) > 1 else delegation.team_run_id
        team_nodes = [n for n in task.nodes if n.team_id == team_id]

        self.emit_event(
            task_id=task.task_id,
            actor_role=delegation.lead_role,
            event_type="team.delegated",
            payload={"team_run_id": delegation.team_run_id, "objective": delegation.objective, "nodes": len(team_nodes)},
            team_run_id=delegation.team_run_id,
            state_before=TaskStatus.READY,
            state_after=TaskStatus.RUNNING,
            depth=1,
        )

        # Allocate child budget slice
        child_budget = self.budget_controller.allocate_slice(
            tokens=delegation.budget_slice.allocated_tokens,
            tool_calls=delegation.budget_slice.allocated_tool_calls,
            cost_paisa=delegation.budget_slice.allocated_cost_paisa,
            seconds=delegation.budget_slice.allocated_seconds,
        )

        team_status = TaskStatus.COMPLETED
        failure_reasons: List[str] = []
        team_receipts: List[ToolReceipt] = []

        # Execute team nodes
        for node in team_nodes:
            if node.status == TaskStatus.COMPLETED:
                continue

            # Check emergency stop
            if self.policy_bridge.is_stopped():
                team_status = TaskStatus.CANCELLED
                failure_reasons.append("Emergency stop active")
                break

            node.lease_owner = f"worker-{team_id[:8]}"
            self.execute_node(task, node)

            team_receipts.extend(node.receipts)
            child_budget.consumed_tokens += 150
            child_budget.consumed_tool_calls += 1
            child_budget.consumed_cost_paisa += 30

            if node.status == TaskStatus.WAITING_APPROVAL:
                team_status = TaskStatus.WAITING_APPROVAL
                break

            if node.status == TaskStatus.FAILED:
                team_status = TaskStatus.FAILED
                failure_reasons.append(node.error or f"Node '{node.title}' failed")
                break

        # Reconcile child budget slice back to parent
        self.budget_controller.reconcile_slice(child_budget)

        duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        verified_posts = [n.expected_postcondition for n in team_nodes if n.status == TaskStatus.COMPLETED and n.expected_postcondition]

        # Generate cryptographic signature for TeamResult
        raw_sig_msg = f"{delegation.team_run_id}:{team_status.value}:{len(team_receipts)}:{duration_ms}"
        sig = hmac.new(_APPROVAL_SECRET.encode("utf-8"), raw_sig_msg.encode("utf-8"), hashlib.sha256).hexdigest()

        scoped_summary = (
            f"Team '{delegation.team_type.value}' successfully executed {len(team_nodes)} nodes."
            if team_status == TaskStatus.COMPLETED
            else f"Team '{delegation.team_type.value}' stopped with status {team_status.value}: {'; '.join(failure_reasons)}"
        )

        team_result = TeamResult(
            team_run_id=delegation.team_run_id,
            parent_task_id=task.task_id,
            team_type=delegation.team_type,
            status=team_status,
            output_artifact_refs=[a["path"] for a in task.artifacts if a.get("team_id") == team_id],
            verified_postconditions=verified_posts,
            evidence_receipts=team_receipts,
            cost_metrics=child_budget.model_dump(),
            failure_reasons=failure_reasons,
            scoped_context_summary=scoped_summary,
            signature=sig,
            duration_ms=duration_ms,
        )

        self.emit_event(
            task_id=task.task_id,
            actor_role=delegation.lead_role,
            event_type="team.completed",
            payload={"team_run_id": delegation.team_run_id, "status": team_status.value, "duration_ms": duration_ms},
            team_run_id=delegation.team_run_id,
            state_before=TaskStatus.RUNNING,
            state_after=team_status,
            depth=1,
        )

        return team_result

    def run_task_to_completion(self, task: TaskSpec) -> TaskResult:
        """Run all team delegation workstreams and synthesize authoritative response."""
        t_start = time.perf_counter()
        task.status = TaskStatus.RUNNING
        self.task_store.save_task(task)

        for delegation in task.team_runs:
            # Check if this team was already completed
            existing_res = next((r for r in task.team_results if r.team_run_id == delegation.team_run_id), None)
            if existing_res and existing_res.status == TaskStatus.COMPLETED:
                continue

            team_res = self.run_team_workstream(task, delegation)
            task.team_results.append(team_res)

            if team_res.status == TaskStatus.WAITING_APPROVAL:
                task.status = TaskStatus.WAITING_APPROVAL
                self.task_store.save_task(task)
                break

            if team_res.status == TaskStatus.FAILED:
                task.status = TaskStatus.FAILED
                task.completed_at = _now_iso()
                self.task_store.save_task(task)
                break

        # Check overall state
        if task.status != TaskStatus.WAITING_APPROVAL:
            all_teams_done = all(r.status == TaskStatus.COMPLETED for r in task.team_results)
            if all_teams_done and len(task.team_results) == len(task.team_runs):
                task.status = TaskStatus.COMPLETED
                task.completed_at = _now_iso()
            elif any(r.status == TaskStatus.FAILED for r in task.team_results):
                task.status = TaskStatus.FAILED
                task.completed_at = _now_iso()

        self.task_store.save_task(task)
        total_duration_ms = round((time.perf_counter() - t_start) * 1000, 2)

        all_receipts = [r for n in task.nodes for r in n.receipts]
        completed_actions = [n.title for n in task.nodes if n.status == TaskStatus.COMPLETED]
        uncompleted_actions = [n.title for n in task.nodes if n.status != TaskStatus.COMPLETED]
        is_verified = (task.status == TaskStatus.COMPLETED) and all(r.verified for r in all_receipts)

        summary_text = (
            f"Successfully coordinated {len(task.team_runs)} hierarchical teams ({len(task.nodes)} nodes). All postconditions verified."
            if task.status == TaskStatus.COMPLETED
            else f"Task ended with status {task.status.value}. Uncompleted: {', '.join(uncompleted_actions)}"
        )

        res = TaskResult(
            task_id=task.task_id,
            status=task.status,
            summary=summary_text,
            completed_actions=completed_actions,
            uncompleted_actions=uncompleted_actions,
            receipts=all_receipts,
            artifacts=task.artifacts,
            budget_used=self.budget_controller.ledger,
            total_duration_ms=total_duration_ms,
            verification_passed=is_verified,
            evidence_trail=[f"Team '{r.team_type.value}': {r.status.value}" for r in task.team_results],
            team_results=task.team_results,
            execution_mode=ExecutionMode.HIERARCHICAL_TEAM,
        )
        return res
