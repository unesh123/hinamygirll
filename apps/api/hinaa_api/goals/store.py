"""
HINAA OS — Phase 14: Goal Engine Authoritative Storage
SQLite WAL-backed persistent storage for Goals, Plan Versions, Milestone DAGs, Evidence Receipts,
Replanning Decisions, Parameter-Bound Approvals, Self-Model Capabilities, and Quarantined Reflections.
"""

from __future__ import annotations

import json
import logging
import sqlite3

from ..persistence import sqlcompat
import time
from typing import Any, Dict, List, Optional, Tuple

from .contracts import (
    CostCategory,
    EvidenceReceipt,
    GoalApprovalRequest,
    GoalSpec,
    GoalStatus,
    Milestone,
    MilestoneStatus,
    PlanVersion,
    QuarantinedReflection,
    ReplanDecision,
    RiskTier,
    RootCauseType,
    SelfModelCapability,
)

logger = logging.getLogger(__name__)


class GoalStore:
    """Authoritative persistence for multi-stage goals, milestone DAGs, and self-correction."""

    def __init__(self, db_path: str = "hinaa_autopilot.db"):
        self.db_path = db_path
        self._pg = sqlcompat.pg_target(db_path, is_default=db_path == "hinaa_autopilot.db")
        self._mem_conn: Optional[sqlite3.Connection] = None
        if self.db_path == ":memory:":
            self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._mem_conn.row_factory = sqlite3.Row
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._mem_conn is not None:
            return self._mem_conn
        if self._pg:
            return sqlcompat.connect_pg(self._pg)
        conn = sqlite3.connect(self.db_path, timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self) -> None:
        conn = self._get_connection()
        try:
            with conn:
                # 1. Goals Table
                conn.execute("""
                CREATE TABLE IF NOT EXISTS goals (
                    goal_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    origin TEXT NOT NULL,
                    authorized_scope_json TEXT NOT NULL,
                    priority INTEGER NOT NULL DEFAULT 50,
                    risk_tier TEXT NOT NULL,
                    time_horizon_seconds REAL NOT NULL,
                    deadline_utc REAL,
                    success_criteria_json TEXT NOT NULL,
                    stop_conditions_json TEXT NOT NULL,
                    budget_paisa INTEGER NOT NULL,
                    budget_tokens INTEGER NOT NULL,
                    consumed_paisa INTEGER NOT NULL DEFAULT 0,
                    consumed_tokens INTEGER NOT NULL DEFAULT 0,
                    source_refs_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    active_plan_version INTEGER NOT NULL DEFAULT 1,
                    replan_count INTEGER NOT NULL DEFAULT 0,
                    max_replans INTEGER NOT NULL DEFAULT 3,
                    created_at_utc REAL NOT NULL,
                    last_reviewed_at_utc REAL NOT NULL,
                    completed_at_utc REAL,
                    termination_reason TEXT,
                    metadata_json TEXT
                )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_goals_tenant ON goals(tenant_id, user_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status, priority)")

                # 2. Plan Versions Table
                conn.execute("""
                CREATE TABLE IF NOT EXISTS goal_plans (
                    plan_version_id TEXT PRIMARY KEY,
                    goal_id TEXT NOT NULL,
                    version_number INTEGER NOT NULL,
                    parent_version_id TEXT,
                    edges_json TEXT NOT NULL,
                    reason_for_change TEXT,
                    triggering_evidence_receipt_id TEXT,
                    verification_reserve_paisa INTEGER NOT NULL DEFAULT 500,
                    verification_reserve_tokens INTEGER NOT NULL DEFAULT 2000,
                    created_at_utc REAL NOT NULL,
                    FOREIGN KEY (goal_id) REFERENCES goals(goal_id) ON DELETE CASCADE
                )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_plans_goal ON goal_plans(goal_id, version_number)")

                # 3. Milestones Table
                conn.execute("""
                CREATE TABLE IF NOT EXISTS goal_milestones (
                    milestone_id TEXT NOT NULL,
                    goal_id TEXT NOT NULL,
                    plan_version_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    inputs_json TEXT NOT NULL,
                    outputs_json TEXT NOT NULL,
                    prerequisites_json TEXT NOT NULL,
                    preconditions_json TEXT NOT NULL,
                    exit_criteria_json TEXT NOT NULL,
                    evidence_requirements_json TEXT NOT NULL,
                    estimated_paisa INTEGER NOT NULL DEFAULT 0,
                    estimated_tokens INTEGER NOT NULL DEFAULT 0,
                    actual_paisa INTEGER NOT NULL DEFAULT 0,
                    actual_tokens INTEGER NOT NULL DEFAULT 0,
                    cost_category TEXT NOT NULL,
                    deadline_utc REAL,
                    risks_json TEXT NOT NULL,
                    fallbacks_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    assigned_role TEXT NOT NULL DEFAULT 'engineer',
                    execution_mode TEXT NOT NULL DEFAULT 'single_agent',
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    max_retries INTEGER NOT NULL DEFAULT 2,
                    started_at_utc REAL,
                    completed_at_utc REAL,
                    failure_reason TEXT,
                    PRIMARY KEY (milestone_id, plan_version_id),
                    FOREIGN KEY (goal_id) REFERENCES goals(goal_id) ON DELETE CASCADE
                )
                """)
                if self._pg:
                    # Milestone order is insertion order; SQLite gets it from rowid.
                    conn.execute("ALTER TABLE goal_milestones ADD COLUMN IF NOT EXISTS row_seq BIGSERIAL")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_milestones_goal_ver ON goal_milestones(goal_id, plan_version_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_milestones_status ON goal_milestones(status)")

                # 4. Evidence Receipts Table
                conn.execute("""
                CREATE TABLE IF NOT EXISTS evidence_receipts (
                    receipt_id TEXT PRIMARY KEY,
                    milestone_id TEXT NOT NULL,
                    goal_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    exit_code INTEGER NOT NULL DEFAULT 0,
                    output_hash TEXT NOT NULL,
                    source_provenance_json TEXT NOT NULL,
                    verified_by_qa INTEGER NOT NULL DEFAULT 0,
                    timestamp_utc REAL NOT NULL,
                    is_valid INTEGER NOT NULL DEFAULT 1,
                    raw_snippet TEXT,
                    signature TEXT,
                    FOREIGN KEY (goal_id) REFERENCES goals(goal_id) ON DELETE CASCADE
                )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_receipts_milestone ON evidence_receipts(milestone_id)")

                # 5. Replan Decisions Table
                conn.execute("""
                CREATE TABLE IF NOT EXISTS replan_decisions (
                    replan_id TEXT PRIMARY KEY,
                    goal_id TEXT NOT NULL,
                    prior_plan_version INTEGER NOT NULL,
                    new_plan_version INTEGER NOT NULL,
                    root_cause TEXT NOT NULL,
                    trigger_evidence_id TEXT,
                    explanation_en TEXT NOT NULL,
                    explanation_ne TEXT NOT NULL,
                    explanation_romanized TEXT NOT NULL,
                    superseded_milestone_ids_json TEXT NOT NULL,
                    reused_milestone_ids_json TEXT NOT NULL,
                    added_milestone_ids_json TEXT NOT NULL,
                    created_at_utc REAL NOT NULL,
                    FOREIGN KEY (goal_id) REFERENCES goals(goal_id) ON DELETE CASCADE
                )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_replans_goal ON replan_decisions(goal_id)")

                # 6. Approvals Table
                conn.execute("""
                CREATE TABLE IF NOT EXISTS goal_approvals (
                    approval_id TEXT PRIMARY KEY,
                    goal_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    resource TEXT NOT NULL,
                    amount_paisa INTEGER NOT NULL DEFAULT 0,
                    recipient TEXT,
                    nonce TEXT NOT NULL UNIQUE,
                    expires_at_utc REAL NOT NULL,
                    is_consumed INTEGER NOT NULL DEFAULT 0,
                    hmac_signature TEXT NOT NULL,
                    FOREIGN KEY (goal_id) REFERENCES goals(goal_id) ON DELETE CASCADE
                )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_approvals_goal ON goal_approvals(goal_id, is_consumed)")

                # 7. Self-Model Capabilities Table
                conn.execute("""
                CREATE TABLE IF NOT EXISTS self_model_capabilities (
                    capability_id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    is_available INTEGER NOT NULL DEFAULT 1,
                    last_checked_utc REAL NOT NULL,
                    error_details TEXT,
                    rate_limit_info_json TEXT NOT NULL,
                    is_mock INTEGER NOT NULL DEFAULT 0
                )
                """)

                # 8. Quarantined Reflections Table
                conn.execute("""
                CREATE TABLE IF NOT EXISTS quarantined_reflections (
                    reflection_id TEXT PRIMARY KEY,
                    goal_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    lesson TEXT NOT NULL,
                    trigger_failure TEXT NOT NULL,
                    corrective_action TEXT NOT NULL,
                    source_receipts_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PENDING_REVIEW',
                    created_at_utc REAL NOT NULL,
                    FOREIGN KEY (goal_id) REFERENCES goals(goal_id) ON DELETE CASCADE
                )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_reflections_tenant ON quarantined_reflections(tenant_id, status)")
        finally:
            if self._mem_conn is None:
                conn.close()

    # ── Goals CRUD ──

    def save_goal(self, goal: GoalSpec) -> None:
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("""
                INSERT INTO goals (
                    goal_id, tenant_id, user_id, project_id, title, description, origin,
                    authorized_scope_json, priority, risk_tier, time_horizon_seconds, deadline_utc,
                    success_criteria_json, stop_conditions_json, budget_paisa, budget_tokens,
                    consumed_paisa, consumed_tokens, source_refs_json, status, active_plan_version,
                    replan_count, max_replans, created_at_utc, last_reviewed_at_utc, completed_at_utc,
                    termination_reason, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(goal_id) DO UPDATE SET
                    title=excluded.title,
                    description=excluded.description,
                    authorized_scope_json=excluded.authorized_scope_json,
                    priority=excluded.priority,
                    risk_tier=excluded.risk_tier,
                    time_horizon_seconds=excluded.time_horizon_seconds,
                    deadline_utc=excluded.deadline_utc,
                    success_criteria_json=excluded.success_criteria_json,
                    stop_conditions_json=excluded.stop_conditions_json,
                    budget_paisa=excluded.budget_paisa,
                    budget_tokens=excluded.budget_tokens,
                    consumed_paisa=excluded.consumed_paisa,
                    consumed_tokens=excluded.consumed_tokens,
                    source_refs_json=excluded.source_refs_json,
                    status=excluded.status,
                    active_plan_version=excluded.active_plan_version,
                    replan_count=excluded.replan_count,
                    last_reviewed_at_utc=excluded.last_reviewed_at_utc,
                    completed_at_utc=excluded.completed_at_utc,
                    termination_reason=excluded.termination_reason,
                    metadata_json=excluded.metadata_json
                """, (
                    goal.goal_id,
                    goal.tenant_id,
                    goal.user_id,
                    goal.project_id,
                    goal.title,
                    goal.description,
                    goal.origin,
                    json.dumps(goal.authorized_scope),
                    goal.priority,
                    goal.risk_tier.value,
                    goal.time_horizon_seconds,
                    goal.deadline_utc,
                    json.dumps(goal.success_criteria),
                    json.dumps(goal.stop_conditions),
                    goal.budget_paisa,
                    goal.budget_tokens,
                    goal.consumed_paisa,
                    goal.consumed_tokens,
                    json.dumps(goal.source_refs),
                    goal.status.value,
                    goal.active_plan_version,
                    goal.replan_count,
                    goal.max_replans,
                    goal.created_at_utc,
                    goal.last_reviewed_at_utc,
                    goal.completed_at_utc,
                    goal.termination_reason,
                    json.dumps(goal.metadata),
                ))
        finally:
            if self._mem_conn is None:
                conn.close()

    def get_goal(self, goal_id: str) -> Optional[GoalSpec]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM goals WHERE goal_id = ?", (goal_id,))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_goal(row)
        finally:
            if self._mem_conn is None:
                conn.close()

    def list_goals(
        self,
        tenant_id: str,
        status: Optional[GoalStatus] = None,
        limit: int = 50,
    ) -> List[GoalSpec]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            if status:
                cur.execute(
                    "SELECT * FROM goals WHERE tenant_id = ? AND status = ? ORDER BY priority DESC, created_at_utc DESC LIMIT ?",
                    (tenant_id, status.value, limit),
                )
            else:
                cur.execute(
                    "SELECT * FROM goals WHERE tenant_id = ? ORDER BY priority DESC, created_at_utc DESC LIMIT ?",
                    (tenant_id, limit),
                )
            rows = cur.fetchall()
            return [self._row_to_goal(r) for r in rows]
        finally:
            if self._mem_conn is None:
                conn.close()

    # ── Plan Version & Milestones ──

    def save_plan_version(self, plan: PlanVersion) -> None:
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("""
                INSERT INTO goal_plans (
                    plan_version_id, goal_id, version_number, parent_version_id,
                    edges_json, reason_for_change, triggering_evidence_receipt_id,
                    verification_reserve_paisa, verification_reserve_tokens, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(plan_version_id) DO UPDATE SET
                    edges_json=excluded.edges_json,
                    reason_for_change=excluded.reason_for_change,
                    triggering_evidence_receipt_id=excluded.triggering_evidence_receipt_id
                """, (
                    plan.plan_version_id,
                    plan.goal_id,
                    plan.version_number,
                    plan.parent_version_id,
                    json.dumps(plan.edges),
                    plan.reason_for_change,
                    plan.triggering_evidence_receipt_id,
                    plan.verification_reserve_paisa,
                    plan.verification_reserve_tokens,
                    plan.created_at_utc,
                ))

                for ms in plan.milestones:
                    self._save_milestone_in_tx(conn, ms, plan.plan_version_id)
        finally:
            if self._mem_conn is None:
                conn.close()

    def _save_milestone_in_tx(self, conn: sqlite3.Connection, ms: Milestone, plan_version_id: str) -> None:
        conn.execute("""
        INSERT INTO goal_milestones (
            milestone_id, goal_id, plan_version_id, title, description,
            inputs_json, outputs_json, prerequisites_json, preconditions_json,
            exit_criteria_json, evidence_requirements_json, estimated_paisa,
            estimated_tokens, actual_paisa, actual_tokens, cost_category,
            deadline_utc, risks_json, fallbacks_json, status, assigned_role,
            execution_mode, retry_count, max_retries, started_at_utc, completed_at_utc, failure_reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(milestone_id, plan_version_id) DO UPDATE SET
            status=excluded.status,
            outputs_json=excluded.outputs_json,
            actual_paisa=excluded.actual_paisa,
            actual_tokens=excluded.actual_tokens,
            retry_count=excluded.retry_count,
            started_at_utc=excluded.started_at_utc,
            completed_at_utc=excluded.completed_at_utc,
            failure_reason=excluded.failure_reason
        """, (
            ms.milestone_id,
            ms.goal_id,
            plan_version_id,
            ms.title,
            ms.description,
            json.dumps(ms.inputs),
            json.dumps(ms.outputs),
            json.dumps(ms.prerequisites),
            json.dumps(ms.preconditions),
            json.dumps(ms.exit_criteria),
            json.dumps(ms.evidence_requirements),
            ms.estimated_paisa,
            ms.estimated_tokens,
            ms.actual_paisa,
            ms.actual_tokens,
            ms.cost_category.value,
            ms.deadline_utc,
            json.dumps(ms.risks),
            json.dumps(ms.fallbacks),
            ms.status.value,
            ms.assigned_role,
            ms.execution_mode,
            ms.retry_count,
            ms.max_retries,
            ms.started_at_utc,
            ms.completed_at_utc,
            ms.failure_reason,
        ))

    def get_plan_version(self, goal_id: str, version_number: int) -> Optional[PlanVersion]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM goal_plans WHERE goal_id = ? AND version_number = ?", (goal_id, version_number))
            p_row = cur.fetchone()
            if not p_row:
                return None
            plan_version_id = p_row["plan_version_id"]

            cur.execute(
                f"SELECT * FROM goal_milestones WHERE plan_version_id = ? ORDER BY {'row_seq' if self._pg else 'rowid'}",
                (plan_version_id,),
            )
            ms_rows = cur.fetchall()
            milestones = [self._row_to_milestone(conn, r) for r in ms_rows]

            return PlanVersion(
                plan_version_id=p_row["plan_version_id"],
                goal_id=p_row["goal_id"],
                version_number=p_row["version_number"],
                parent_version_id=p_row["parent_version_id"],
                milestones=milestones,
                edges=json.loads(p_row["edges_json"]),
                reason_for_change=p_row["reason_for_change"],
                triggering_evidence_receipt_id=p_row["triggering_evidence_receipt_id"],
                verification_reserve_paisa=p_row["verification_reserve_paisa"],
                verification_reserve_tokens=p_row["verification_reserve_tokens"],
                created_at_utc=p_row["created_at_utc"],
            )
        finally:
            if self._mem_conn is None:
                conn.close()

    def update_milestone_status(
        self,
        milestone_id: str,
        status: MilestoneStatus,
        failure_reason: Optional[str] = None,
        actual_paisa: int = 0,
        actual_tokens: int = 0,
        started_at_utc: Optional[float] = None,
    ) -> None:
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("""
                UPDATE goal_milestones SET
                    status = ?,
                    failure_reason = ?,
                    actual_paisa = actual_paisa + ?,
                    actual_tokens = actual_tokens + ?,
                    started_at_utc = COALESCE(?, started_at_utc),
                    completed_at_utc = CASE WHEN ? IN ('VERIFIED', 'FAILED', 'BLOCKED', 'SKIPPED') THEN ? ELSE completed_at_utc END
                WHERE milestone_id = ?
                """, (
                    status.value,
                    failure_reason,
                    actual_paisa,
                    actual_tokens,
                    started_at_utc,
                    status.value,
                    time.time(),
                    milestone_id,
                ))
        finally:
            if self._mem_conn is None:
                conn.close()

    # ── Evidence Receipts ──

    def save_evidence_receipt(self, receipt: EvidenceReceipt) -> None:
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("""
                INSERT INTO evidence_receipts (
                    receipt_id, milestone_id, goal_id, tool_name, exit_code,
                    output_hash, source_provenance_json, verified_by_qa,
                    timestamp_utc, is_valid, raw_snippet, signature
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(receipt_id) DO NOTHING
                """, (
                    receipt.receipt_id,
                    receipt.milestone_id,
                    receipt.goal_id,
                    receipt.tool_name,
                    receipt.exit_code,
                    receipt.output_hash,
                    json.dumps(receipt.source_provenance),
                    1 if receipt.verified_by_qa else 0,
                    receipt.timestamp_utc,
                    1 if receipt.is_valid else 0,
                    receipt.raw_snippet,
                    receipt.signature,
                ))
        finally:
            if self._mem_conn is None:
                conn.close()

    def list_evidence_receipts(self, goal_id: str, milestone_id: Optional[str] = None) -> List[EvidenceReceipt]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            if milestone_id:
                cur.execute(
                    "SELECT * FROM evidence_receipts WHERE goal_id = ? AND milestone_id = ? ORDER BY timestamp_utc ASC",
                    (goal_id, milestone_id),
                )
            else:
                cur.execute(
                    "SELECT * FROM evidence_receipts WHERE goal_id = ? ORDER BY timestamp_utc ASC",
                    (goal_id,),
                )
            rows = cur.fetchall()
            return [self._row_to_receipt(r) for r in rows]
        finally:
            if self._mem_conn is None:
                conn.close()

    # ── Replan Decisions ──

    def save_replan_decision(self, decision: ReplanDecision) -> None:
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("""
                INSERT INTO replan_decisions (
                    replan_id, goal_id, prior_plan_version, new_plan_version,
                    root_cause, trigger_evidence_id, explanation_en, explanation_ne,
                    explanation_romanized, superseded_milestone_ids_json,
                    reused_milestone_ids_json, added_milestone_ids_json, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(replan_id) DO NOTHING
                """, (
                    decision.replan_id,
                    decision.goal_id,
                    decision.prior_plan_version,
                    decision.new_plan_version,
                    decision.root_cause.value,
                    decision.trigger_evidence_id,
                    decision.explanation_en,
                    decision.explanation_ne,
                    decision.explanation_romanized,
                    json.dumps(decision.superseded_milestone_ids),
                    json.dumps(decision.reused_milestone_ids),
                    json.dumps(decision.added_milestone_ids),
                    decision.created_at_utc,
                ))
        finally:
            if self._mem_conn is None:
                conn.close()

    def list_replans(self, goal_id: str) -> List[ReplanDecision]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM replan_decisions WHERE goal_id = ? ORDER BY new_plan_version ASC", (goal_id,))
            rows = cur.fetchall()
            return [
                ReplanDecision(
                    replan_id=r["replan_id"],
                    goal_id=r["goal_id"],
                    prior_plan_version=r["prior_plan_version"],
                    new_plan_version=r["new_plan_version"],
                    root_cause=RootCauseType(r["root_cause"]),
                    trigger_evidence_id=r["trigger_evidence_id"],
                    explanation_en=r["explanation_en"],
                    explanation_ne=r["explanation_ne"],
                    explanation_romanized=r["explanation_romanized"],
                    superseded_milestone_ids=json.loads(r["superseded_milestone_ids_json"]),
                    reused_milestone_ids=json.loads(r["reused_milestone_ids_json"]),
                    added_milestone_ids=json.loads(r["added_milestone_ids_json"]),
                    created_at_utc=r["created_at_utc"],
                )
                for r in rows
            ]
        finally:
            if self._mem_conn is None:
                conn.close()

    # ── Approvals ──

    def save_approval(self, approval: GoalApprovalRequest) -> None:
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("""
                INSERT INTO goal_approvals (
                    approval_id, goal_id, tenant_id, action_type, resource,
                    amount_paisa, recipient, nonce, expires_at_utc, is_consumed, hmac_signature
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(approval_id) DO UPDATE SET
                    is_consumed=excluded.is_consumed
                """, (
                    approval.approval_id,
                    approval.goal_id,
                    approval.tenant_id,
                    approval.action_type,
                    approval.resource,
                    approval.amount_paisa,
                    approval.recipient,
                    approval.nonce,
                    approval.expires_at_utc,
                    1 if approval.is_consumed else 0,
                    approval.hmac_signature,
                ))
        finally:
            if self._mem_conn is None:
                conn.close()

    def get_approval(self, approval_id: str) -> Optional[GoalApprovalRequest]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM goal_approvals WHERE approval_id = ?", (approval_id,))
            r = cur.fetchone()
            if not r:
                return None
            return GoalApprovalRequest(
                approval_id=r["approval_id"],
                goal_id=r["goal_id"],
                tenant_id=r["tenant_id"],
                action_type=r["action_type"],
                resource=r["resource"],
                amount_paisa=r["amount_paisa"],
                recipient=r["recipient"],
                nonce=r["nonce"],
                expires_at_utc=r["expires_at_utc"],
                is_consumed=bool(r["is_consumed"]),
                hmac_signature=r["hmac_signature"],
            )
        finally:
            if self._mem_conn is None:
                conn.close()

    def consume_approval(self, approval_id: str) -> bool:
        """Atomically marks an approval as consumed. Returns True if successfully consumed."""
        conn = self._get_connection()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE goal_approvals SET is_consumed = 1 WHERE approval_id = ? AND is_consumed = 0",
                    (approval_id,),
                )
                return cur.rowcount > 0
        finally:
            if self._mem_conn is None:
                conn.close()

    # ── Self-Model Capabilities ──

    def save_capability(self, cap: SelfModelCapability) -> None:
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("""
                INSERT INTO self_model_capabilities (
                    capability_id, category, provider, is_available,
                    last_checked_utc, error_details, rate_limit_info_json, is_mock
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(capability_id) DO UPDATE SET
                    is_available=excluded.is_available,
                    last_checked_utc=excluded.last_checked_utc,
                    error_details=excluded.error_details,
                    rate_limit_info_json=excluded.rate_limit_info_json,
                    is_mock=excluded.is_mock
                """, (
                    cap.capability_id,
                    cap.category,
                    cap.provider,
                    1 if cap.is_available else 0,
                    cap.last_checked_utc,
                    cap.error_details,
                    json.dumps(cap.rate_limit_info),
                    1 if cap.is_mock else 0,
                ))
        finally:
            if self._mem_conn is None:
                conn.close()

    def get_capability(self, capability_id: str) -> Optional[SelfModelCapability]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM self_model_capabilities WHERE capability_id = ?", (capability_id,))
            r = cur.fetchone()
            if not r:
                return None
            return SelfModelCapability(
                capability_id=r["capability_id"],
                category=r["category"],
                provider=r["provider"],
                is_available=bool(r["is_available"]),
                last_checked_utc=r["last_checked_utc"],
                error_details=r["error_details"],
                rate_limit_info=json.loads(r["rate_limit_info_json"]),
                is_mock=bool(r["is_mock"]),
            )
        finally:
            if self._mem_conn is None:
                conn.close()

    def list_capabilities(self) -> List[SelfModelCapability]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM self_model_capabilities ORDER BY category ASC")
            rows = cur.fetchall()
            return [
                SelfModelCapability(
                    capability_id=r["capability_id"],
                    category=r["category"],
                    provider=r["provider"],
                    is_available=bool(r["is_available"]),
                    last_checked_utc=r["last_checked_utc"],
                    error_details=r["error_details"],
                    rate_limit_info=json.loads(r["rate_limit_info_json"]),
                    is_mock=bool(r["is_mock"]),
                )
                for r in rows
            ]
        finally:
            if self._mem_conn is None:
                conn.close()

    # ── Quarantined Reflections ──

    def save_reflection(self, refl: QuarantinedReflection) -> None:
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("""
                INSERT INTO quarantined_reflections (
                    reflection_id, goal_id, tenant_id, lesson, trigger_failure,
                    corrective_action, source_receipts_json, status, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(reflection_id) DO UPDATE SET
                    status=excluded.status
                """, (
                    refl.reflection_id,
                    refl.goal_id,
                    refl.tenant_id,
                    refl.lesson,
                    refl.trigger_failure,
                    refl.corrective_action,
                    json.dumps(refl.source_receipts),
                    refl.status,
                    refl.created_at_utc,
                ))
        finally:
            if self._mem_conn is None:
                conn.close()

    def list_reflections(self, tenant_id: str, status: Optional[str] = None) -> List[QuarantinedReflection]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            if status:
                cur.execute(
                    "SELECT * FROM quarantined_reflections WHERE tenant_id = ? AND status = ? ORDER BY created_at_utc DESC",
                    (tenant_id, status),
                )
            else:
                cur.execute(
                    "SELECT * FROM quarantined_reflections WHERE tenant_id = ? ORDER BY created_at_utc DESC",
                    (tenant_id,),
                )
            rows = cur.fetchall()
            return [
                QuarantinedReflection(
                    reflection_id=r["reflection_id"],
                    goal_id=r["goal_id"],
                    tenant_id=r["tenant_id"],
                    lesson=r["lesson"],
                    trigger_failure=r["trigger_failure"],
                    corrective_action=r["corrective_action"],
                    source_receipts=json.loads(r["source_receipts_json"]),
                    status=r["status"],
                    created_at_utc=r["created_at_utc"],
                )
                for r in rows
            ]
        finally:
            if self._mem_conn is None:
                conn.close()

    def delete_goal_and_data(self, goal_id: str) -> None:
        """Deletes a goal and all linked plans, milestones, receipts, and quarantined reflections."""
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("DELETE FROM quarantined_reflections WHERE goal_id = ?", (goal_id,))
                conn.execute("DELETE FROM replan_decisions WHERE goal_id = ?", (goal_id,))
                conn.execute("DELETE FROM evidence_receipts WHERE goal_id = ?", (goal_id,))
                conn.execute("DELETE FROM goal_milestones WHERE goal_id = ?", (goal_id,))
                conn.execute("DELETE FROM goal_plans WHERE goal_id = ?", (goal_id,))
                conn.execute("DELETE FROM goal_approvals WHERE goal_id = ?", (goal_id,))
                conn.execute("DELETE FROM goals WHERE goal_id = ?", (goal_id,))
        finally:
            if self._mem_conn is None:
                conn.close()

    # ── Mappers ──

    def _row_to_goal(self, row: sqlite3.Row) -> GoalSpec:
        return GoalSpec(
            goal_id=row["goal_id"],
            tenant_id=row["tenant_id"],
            user_id=row["user_id"],
            project_id=row["project_id"],
            title=row["title"],
            description=row["description"] or "",
            origin=row["origin"],
            authorized_scope=json.loads(row["authorized_scope_json"]),
            priority=row["priority"],
            risk_tier=RiskTier(row["risk_tier"]),
            time_horizon_seconds=row["time_horizon_seconds"],
            deadline_utc=row["deadline_utc"],
            success_criteria=json.loads(row["success_criteria_json"]),
            stop_conditions=json.loads(row["stop_conditions_json"]),
            budget_paisa=row["budget_paisa"],
            budget_tokens=row["budget_tokens"],
            consumed_paisa=row["consumed_paisa"],
            consumed_tokens=row["consumed_tokens"],
            source_refs=json.loads(row["source_refs_json"]),
            status=GoalStatus(row["status"]),
            active_plan_version=row["active_plan_version"],
            replan_count=row["replan_count"],
            max_replans=row["max_replans"],
            created_at_utc=row["created_at_utc"],
            last_reviewed_at_utc=row["last_reviewed_at_utc"],
            completed_at_utc=row["completed_at_utc"],
            termination_reason=row["termination_reason"],
            metadata=json.loads(row["metadata_json"] or "{}"),
        )

    def _row_to_milestone(self, conn: sqlite3.Connection, r: sqlite3.Row) -> Milestone:
        # Load evidence receipts
        cur = conn.cursor()
        cur.execute("SELECT * FROM evidence_receipts WHERE milestone_id = ?", (r["milestone_id"],))
        receipt_rows = cur.fetchall()
        receipts = [self._row_to_receipt(rec) for rec in receipt_rows]

        return Milestone(
            milestone_id=r["milestone_id"],
            goal_id=r["goal_id"],
            title=r["title"],
            description=r["description"] or "",
            inputs=json.loads(r["inputs_json"]),
            outputs=json.loads(r["outputs_json"]),
            prerequisites=json.loads(r["prerequisites_json"]),
            preconditions=json.loads(r["preconditions_json"]),
            exit_criteria=json.loads(r["exit_criteria_json"]),
            evidence_requirements=json.loads(r["evidence_requirements_json"]),
            estimated_paisa=r["estimated_paisa"],
            estimated_tokens=r["estimated_tokens"],
            actual_paisa=r["actual_paisa"],
            actual_tokens=r["actual_tokens"],
            cost_category=CostCategory(r["cost_category"]),
            deadline_utc=r["deadline_utc"],
            risks=json.loads(r["risks_json"]),
            fallbacks=json.loads(r["fallbacks_json"]),
            status=MilestoneStatus(r["status"]),
            assigned_role=r["assigned_role"],
            execution_mode=r["execution_mode"],
            evidence_receipts=receipts,
            retry_count=r["retry_count"],
            max_retries=r["max_retries"],
            started_at_utc=r["started_at_utc"],
            completed_at_utc=r["completed_at_utc"],
            failure_reason=r["failure_reason"],
        )

    def _row_to_receipt(self, r: sqlite3.Row) -> EvidenceReceipt:
        return EvidenceReceipt(
            receipt_id=r["receipt_id"],
            milestone_id=r["milestone_id"],
            goal_id=r["goal_id"],
            tool_name=r["tool_name"],
            exit_code=r["exit_code"],
            output_hash=r["output_hash"],
            source_provenance=json.loads(r["source_provenance_json"]),
            verified_by_qa=bool(r["verified_by_qa"]),
            timestamp_utc=r["timestamp_utc"],
            is_valid=bool(r["is_valid"]),
            raw_snippet=r["raw_snippet"],
            signature=r["signature"],
        )
